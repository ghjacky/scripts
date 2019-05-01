import mimetypes


def get_text_file(filepath):
    return filepath if 'text/plain' in mimetypes.guess_type(filepath) else ''


class FilterModule(object):
    def filters(self):
        return {
            'get_text_file': get_text_file
        }
