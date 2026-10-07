from pathlib import Path

basedir = Path(__file__).parent.parent

# BaseConfig
class BaseConfig:
    SECRET_KEY = "qawsedrfgtyhujikolp"
    WTF_CSRF_SECRET_KEY = "azsxdcfvgbhnjmk"