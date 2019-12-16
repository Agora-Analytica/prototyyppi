from .. import instance_path

import re

import pandas as pd
import numpy as np
import joblib

from stop_words import get_stop_words
from voikko.libvoikko import Voikko

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation as LDA

from itertools import chain
from collections import namedtuple
from typing import List, Dict, Tuple
import logging

from cachetools import cached, LRUCache, LFUCache, keys

logger = logging.getLogger(__name__)

TopicComparision = namedtuple("TopicComparision", ["source", "target"])
Topic = namedtuple("Topic", ["id", "term"])

class VoikkoTokenizer():

    """
    Voikko Tokenizer
    ~~~~~~~~~~~~~~~~

    Getting Voikko to work on Windows
    =================================
    - Download voikko DLL into application directory from:
      https://www.puimula.org/htp/testing/voikko-sdk/win-crossbuild/
    - Download and extract dictionary files into `instance/voikko` directory:
      https://www.puimula.org/htp/testing/voikko-snapshot-v5/

      Select one contain morphological data.

    """

    """ Tokenize text """
    def __init__(self, lang="fi"):

        # Voikko dictrionary path.
        dict_path = instance_path() / "voikko"
        path = str(dict_path) if dict_path.exists() else None

        self.stem_map = {}
        self.voikko = Voikko(lang, path=path)
        self.regex_words = re.compile(r"""
            (\w+-(?:\w+)+  # Get wordcharacters conjucated by dash (-)
            |\w{1,}        # OR all word characters len() > 1
            )|(?::[\w]*)   # ignore word characters after colon
        """, re.VERBOSE + re.MULTILINE)
        self.err_treshold = 0.5

    def tokenize(self, text: str) -> List[str]:
        """ Return list of words """
        # Split into paragraphs.
        paragraphs = text.splitlines()
        tokens = chain(*map(self.tokenize_paragraph, paragraphs))

        return tokens

    def tokenize_paragraph(self, sentence, use_suggestions=True):
        """ Tokenize words using :class:`~Voikko`

        ..todo:
            - Detect abbrevations from CAPITAL letters.

        :param use_suggestions:  Should stemming use spell checking.
        """

        # Spell check mistake counters
        err_count = 0

        def _stem(word: str) -> List[str]:
            """ Return :type:`list` of stemmed words.

            If word is found on voikko dataset, uses suggestion to lookup for first candidate.
            """
            nonlocal err_count

            # See: https://github.com/voikko/voikko-sklearn/blob/master/voikko_sklearn.py
            FINNISH_STOPWORD_CLASSES = ["huudahdussana", "seikkasana", "lukusana", "asemosana", "sidesana", "suhdesana"]

            # Check for previous stemming result
            stemmed_word = self.stem_map.get(word, None)
            if stemmed_word is not None:
                return [stemmed_word]

            analysis = self.analyze(word)

            if not analysis:
                # If analyze didn't produce results, try spellcheking
                err_count += 1
                analysis = []

                if use_suggestions:
                    # Get first suggestion.
                    suggested, *xs = self.voikko.suggest(word) or [None]
                    logger.debug(f"Voikko did not found word {word!r}; suggested spelling: {suggested!r}")

                    if suggested is not None:
                        # return tokenized suggestion - It can be two or more words.
                        return self.tokenize_paragraph(suggested, use_suggestions=False)

            # Prefer nimisana over others
            analysis = sorted(analysis, key=lambda x: -1 if x.get('CLASS') in ["nimisana"] else 0)

            for _word in analysis:
                # Find first suitable iteration of word.
                _class = _word.get("CLASS", None)
                if _class not in FINNISH_STOPWORD_CLASSES:
                    baseform = _word.get('BASEFORM').lower()
                    self.stem_map[word] = baseform
                    return [baseform]

            # Fall back to given word.
            self.stem_map[word] = word.lower()
            return [word.lower()]

        # Create list of words from string, separating from non-word characters.
        r = [x for x in re.findall(self.regex_words, sentence.lower()) if x != ""]

        r = [x for x in chain(*map(_stem, r)) if x]
        if len(r) * self.err_treshold < err_count:
            # Too many spelling errors. Presume incorrect language, and disregard paragraph.
            logger.debug("Too many spelling errors: %d out of %d", err_count, len(r))
            return []

        return r

    @cached(LFUCache(maxsize=512))
    def analyze(self, word: str) -> List[Dict]:
        """ Analyze word, returning morhpological data.

            Uses :class:`LFUCache` - least frequently used - cache.
         """
        return self.voikko.analyze(word)

    def __getstate__(self):
        """ Return pickleable attributes.

        :class:`Voikko` can't be serialized, so remove it.
        """

        state = self.__dict__.copy()
        state['voikko_lang'] = self.voikko.listDicts()[0].language
        del state['voikko']
        return state

    def __setstate__(self, state):
        state['voikko'] = Voikko(state['voikko_lang'])
        del state['voikko_lang']
        self.__dict__.update(state)


class TextTopics():
    """
    Text classifier.
    """
    def __init__(self,
                 df: pd.DataFrame,
                 number_topics=50,
                 instance_path=instance_path(),
                 **kwargs):
        self._instance_path = instance_path
        self.number_topics = number_topics
        self.stop_words: List = get_stop_words("fi")
        self._count_vector: CountVectorizer = None
        self._lda: LDA = None
        self.token_cache = {}
        self._tokenizer = None
        self.min_sentence_length = 17

        # `kk` is used in assocation with time periods.
        self.stop_words += ["kk", "voi", "yms", "mm"]

        self.init(df, kwargs)

    def init(self, df: pd.DataFrame, generate_visualization=False, lang="fi"):
        """
        :param df: :class:`~pandas.Dataframe` containing text colums
        :param generate_visualization: Generate visalization of LDA results. Slows down
                                       generation notably.
        :param lang: Language for :class:`~Voikko`
        """
        if self._count_vector and self._lda:
            return True

        file_words = self.instance_path() / "word.dat"
        file_lda = self.instance_path() / "lda.dat"
        file_ldavis = self.instance_path() / "ldavis.html"

        try:
            # Try loading saved lda files.
            self._count_vector = joblib.load(file_words)
            self._lda = joblib.load(file_lda)
        except FileNotFoundError as e:
            logger.exception(e)

            texts = [x for x in df.to_numpy().flatten() if x is not np.NaN]

            # Setup word count vector
            self._count_vector = CountVectorizer(
                tokenizer=self.text_tokenize,
                stop_words=self.stop_words
            )
            count_data = self._count_vector.fit_transform(texts)

            self._lda = LDA(n_components=self.number_topics, n_jobs=-1)
            self._lda.fit(count_data)

            if generate_visualization:
                logger.debug("Generating LDA visualization. This might take a while")
                from pyLDAvis import sklearn as sklearn_lda
                import pyLDAvis

                LDAvis_prepared = sklearn_lda.prepare(self._lda, count_data, self._count_vector)
                pyLDAvis.save_html(LDAvis_prepared, str(file_ldavis))

            joblib.dump(self._count_vector, file_words)
            joblib.dump(self._lda, file_lda)

    def instance_path(self):
        path = self._instance_path / "lda" / str(self.number_topics)
        path.mkdir(exist_ok=True, parents=True)
        return path

    def tokenizer(self):
        if not self._tokenizer:
            self._tokenizer = VoikkoTokenizer("fi")
        return self._tokenizer

    @cached(LRUCache(maxsize=1024))
    def text_tokenize(self, text):
        """ Cached wrapper for `VoikkoTokenizer.tokenize()` """
        return self.tokenizer().tokenize(text)

    def find_talkingpoint(self, candidate: pd.Series) -> str:
        """ Find most suitable sentence from text """
        texts = tuple(candidate.dropna())
        if len(texts) == 0:
            return None

        x = self._get_topics(texts)
        return self.nearest_sentence(x[1], texts)

    def nearest_sentence(self, topics: List[float], texts: List[str]) -> str:
        """
        Find sentence closest to topic.

        TODO: When joining multiple sentences, it should be checked that they are from same paragraph.
        """
        @cached(LFUCache(maxsize=128))
        def lda(sentences):
            count_data = self._count_vector.transform(sentences)
            _lda = self._lda.transform(count_data)
            return _lda

        # Tokenize into sentences.
        sentences = chain(*[re.findall(r"\s*(.+?[\.!?])+", b, re.MULTILINE + re.DOTALL) for b in texts if b.strip() != ""])

        # cleanup sentences.
        sentences = tuple(set(filter(lambda x: len(x) > self.min_sentence_length, map(str.strip, sentences))))
        if len(sentences) == 0:
            return None

        # Find most topical sentence.
        tl_dr = []
        distance = 1.
        prev_sentence = ""
        for current_sentence, m in zip(sentences, lda(sentences)):
            _distance = np.abs(np.mean(topics - m))
            if _distance < distance:
                tl_dr, distance = ([prev_sentence, current_sentence], _distance)
            
            # Previous sentence is to provide context to most suitable sentence.
            prev_sentence = current_sentence

        return " ".join(filter(None, tl_dr))

    def compare_series(self, source: pd.Series, target: pd.Series):
        """
        Compare two text sets.

        First tuple contains topic word not found in :param:`target`, and second tuple
        contains word not found in :param:`source`.

        Note: This result will not be cached. Use :method:`compare_rows()` if possible.
        """
        # Convert them into tuples, so they can be cached.
        _source = tuple(source.dropna())
        _target = tuple(target.dropna())

        return self.compare_count_data(
            *self._get_topics(_source),
            *self._get_topics(_target)
        )

    def compare_rows(self, df: pd.DataFrame, i, l):
        x = self.row_topics(df, i)
        y = self.row_topics(df, l)
        if not x or not y:
            return None

        r = self.compare_count_data(*x, *y)
        return r

    def row_topics(self, df: pd.DataFrame, idx):
        """ Return suitable topics from dataset `df` row :param:`idx` """
        x = tuple(df.loc[idx].dropna())
        if len(x) == 0:
            return None

        return self._get_topics(x)

    @cached(LRUCache(maxsize=512))
    def _get_topics(self, source: List) -> Tuple:

        count_data = self._count_vector.transform(source)
        return (count_data, self._lda.transform(count_data).mean(axis=0))

    def compare_count_data(self, counts_data_source, topics_source, counts_data_target, topics_target) -> Tuple[Tuple[str, int], Tuple[str, int]]:
        diffs = topics_source - topics_target

        topic_max = np.argmax(diffs)
        topic_min = np.argmin(diffs)

        source_words = self.suggest_topic_word(counts_data_source, counts_data_target, topic_max)
        target_words = self.suggest_topic_word(counts_data_target, counts_data_source, topic_min)

        word_for_source = self.suitable_topic_word(source_words) if len(source_words) else None
        word_for_target = self.suitable_topic_word(target_words) if len(target_words) else None

        return TopicComparision(
            source=Topic(id=topic_max, term=word_for_source),
            target=Topic(id=topic_min, term=word_for_target)
        )

    def suggest_topic_word(self, A, B, topic_id: int) -> List[Tuple[int, float]]:
        """ Find relevant word for topic.

        Copares :param:`A` and :param:`B` words, and topic words to find
        suitable word with enough difference between `A` and `B`.

        :param A: :class:`csr_matrix` Target to find word for.
        :param B: :class:`csr_matrix` Comparative target for `A`
        :param topic_id: lda topic id number.

        :return: List of tuples in prominen order.
                 First instance in tuple is word vector feature number, and second is prominence value.
        """
        # Generate sum of used words
        a_sum = A.toarray().sum(0)
        b_sum = B.toarray().sum(0)

        # Topic word, prefering unique ones.
        λ = self._lda.components_[topic_id] / self._lda.components_.sum(0)

        # Remove words from A that B has used too.
        # Note: Doesn't actually remove.
        complement = a_sum - b_sum

        # Use logarithm, so topic words are prefered.
        prominence = np.log(complement) * λ

        # Generate list of words, ordered by prominence
        r = sorted([(i, prominence[i]) for i in prominence.argsort() if prominence[i] != 0 > -np.inf], key=lambda x: x[1], reverse=True)
        return r

    # sequence list is too volatile to be cached.
    def suitable_topic_word(self, seq: List[List[int, ]]) -> str:
        """
        Find first suitable word from :param:`seq` list.

        :param: 1d matrix of word feature indexes. Only first column in row
                is interepted as feature number.
        """
        vector_words = self.vector_words()
        """ Find first suitable word from word list """
        for r in seq:
            word = vector_words[r[0]]
            if self._suitable_topic_word(word):
                return word
        return None

    @cached(LFUCache(maxsize=512))
    def _suitable_topic_word(self, word) -> bool:
        """
        Check if word can be used as topic word

        Accepted word classes:
        :nimi:      Names; Words like `Linux` and `Microsoft`, `Kokoomus`
        :nimisana:  Substantives; like `ihminen`, `maahanmuutto`, `koulutus`, `Kokoomus`
        :laatusana: Adjectives; words like `maksuton`
        :nimisana_laatusana: Adjectives, that are not "real", like `rohkea` or `liberaali`
        :lyhenne:   Abbrevations; Words like `EU`
        :paikannimi:Geographical locations, like `Helsinki`
        :sukunimi:  Last names, like `Kekkonen`
        """

        for morph in self.tokenizer().analyze(word):
            _class = morph.get("CLASS")
            if _class in ["nimi", "nimisana", "nimisana_laatusana", "lyhenne", "paikannimi", "sukunimi"]:
                return True
            else:
                logger.debug("Unsuitable word class %s for word %s", _class, word)

        return False

    def vector_words(self) -> List:
        """ Feature names in CountVector """
        return self._count_vector.get_feature_names()


if __name__ == "__main__":
    import sys
    from pprint import pprint
    v = VoikkoTokenizer()

    tokens = v.tokenize(" ".join(sys.argv[1:]))
    [pprint(sorted(v.analyze(t), key=lambda x: -1 if x.get('CLASS') in ["nimisana"] else 0)) for t in tokens]
