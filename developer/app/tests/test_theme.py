from interface.theme import DEFAULT_THEME_NAME, get_theme, list_theme_names


def test_list_theme_names_includes_default():
    assert DEFAULT_THEME_NAME in list_theme_names()


def test_get_theme_known_name():
    theme = get_theme(DEFAULT_THEME_NAME)
    assert theme.text_primary


def test_get_theme_unknown_name_falls_back_to_default():
    theme = get_theme("does-not-exist")
    assert theme == get_theme(DEFAULT_THEME_NAME)
