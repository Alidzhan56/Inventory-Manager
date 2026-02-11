import os
import json
from flask import session, request, g


def load_translations(lang, app):
    """
    Зареждам JSON файла за съответния език.
    Ако езикът не съществува, падам обратно към DEFAULT_LANG.
    """
    path = os.path.join('translations', f'{lang}.json')

    # ако файлът го няма, ползвам default езика от config
    if not os.path.exists(path):
        path = os.path.join('translations', f"{app.config['DEFAULT_LANG']}.json")

    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def set_language(app):
    """
    Определям текущия език:
    1. ако има ?lang= в URL и е разрешен -> записвам го в session
    2. ако няма нищо в session -> слагам default
    После записвам в g за да е достъпно навсякъде в request-а.
    """
    lang = request.args.get('lang')

    if lang and lang in app.config['LANGUAGES']:
        session['lang'] = lang
    elif 'lang' not in session:
        session['lang'] = app.config['DEFAULT_LANG']

    g.lang = session['lang']
    g.translations = load_translations(g.lang, app)


def _(key):
    """
    Малка helper функция за превод.
    Ако няма превод за даден ключ връщам самия ключ.
    Така никога не чупя страницата.
    """
    try:
        return g.translations.get(key, key)
    except Exception:
        return key
