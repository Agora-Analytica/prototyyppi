# Agora Analytica

Interactive network analysis of political candidates.

## Methology

Network is based on kinship; Distances between candidates – or nodes – is based how similarly they have answered. Similar answers lead to short distances. Answers are weighted on how exceptional this kind of answer is, in regards of question; Rare answers are weighted as more notable – in regards of distance approximation – than common answers. Only closest 3 are noted, and other distances are disregarded.

Text analysis is based on topic clustering. Using LDA, answers are categorized into topics. Comparing topics where two candidates are are furthest apart, links are selected for topics which represents topic into a one – outward – direction. Suitable topic word is selected individually, comparing how likely candidate is to use topic word, and how relevant – salient – word is for that topic.

## Licenses

- **Agora Analytica** [Licensed under MIT](https://github.com/Agora-Analytica/prototyyppi/blob/master/LICENSE).
- [**Yle Vaalidata**](https://yle.fi/uutiset/3-10725384) Licensed under Creative Commons. [Copyright Yle 2019](https://vaalikone.yle.fi/)
- Additional party data from **WikiData**. Lincensed under Creative Commons Zero. Copyright Wikipedia Contributors.
- Names are generated from most popular Finnish names. Nameset copyright Väestörekisterikeskus.

## Authors

- [Teemu Autto](https://github.com/orgs/Agora-Analytica/people/isoteemu)
- [Markus Kauppi](https://github.com/orgs/Agora-Analytica/people/jokukayttajanimi)
- [Joni Nisula](https://github.com/orgs/Agora-Analytica/people/Kyrmy)
- [Sanna Marjamäki](https://github.com/orgs/Agora-Analytica/people/sanmarj)
