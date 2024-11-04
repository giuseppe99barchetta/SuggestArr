# This file is for useful testing functions that are shared across multiple test files.


def _verbose_dict_compare(dict1, dict2, assert_func):
    """Helper function to print out the differences between two dicts. This provides more
    useful error messages than a simple assertEqual."""
    for item in dict1:
        assert_func(dict1[item], dict2[item])

    for item in dict2:
        assert_func(dict1[item], dict2[item])
