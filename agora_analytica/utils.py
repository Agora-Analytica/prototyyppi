
def clamp(number: int, max_value: int, min_value: int) -> int:
    """ Clamp value into a range """
    return max(min(number, max_value), min_value)
