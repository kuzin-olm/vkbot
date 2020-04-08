LOGGER_STATE = 'in_console'

LOGGER = {
    'version': 1,
    'formatters': {
        'my_formatter': {
            'format': '%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        # 'file_handler': {
        #     'class': 'logging.FileHandler',
        #     'formatter': 'my_formatter',
        #     'filename': 'logs.log',
        #     'encoding': 'utf-8'
        # },
        'console_handler': {
            'class': 'logging.StreamHandler',
            'formatter': 'my_formatter'
        }
    },
    'loggers': {
        # 'in_file': {
        #     'handlers': ['file_handler'],
        #     'level': 'DEBUG'
        # },
        'in_console': {
            'handlers': ['console_handler'],
            'level': 'DEBUG'
        }
    }
}
