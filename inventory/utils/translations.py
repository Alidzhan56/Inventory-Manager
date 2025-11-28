import os
import json
from flask import session, request, g

def load_translations(lang, app):
    """Load translations from JSON file based on language code."""
    path = os.path.join('translations', f'{lang}.json')
    if not os.path.exists(path):
        path = os.path.join('translations', f"{app.config['DEFAULT_LANG']}.json")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def set_language(app):
    """Set language preference from query string or session."""
    lang = request.args.get('lang')
    if lang and lang in app.config['LANGUAGES']:
        session['lang'] = lang
    elif 'lang' not in session:
        session['lang'] = app.config['DEFAULT_LANG']
    g.lang = session['lang']
    g.translations = load_translations(g.lang, app)

def _(key):
    """Translation function"""
    try:
        return g.translations.get(key, key)
    except Exception:
        return key