import vdf


def get_hidden_apps(path: str) -> list:
    if not path:
        raise VDFEmptyPathException('path is empty')
    hidden_apps = []
    try:
        with open(path, encoding='utf-8') as fp:
            cfg = vdf.load(fp)
            apps: dict = cfg['UserRoamingConfigStore']['Software']['Valve']['Steam']['Apps']
            for appid, parameters in apps.items():
                if parameters.get('hidden', None):
                    hidden_apps.append(int(appid))
            return hidden_apps
    except (KeyError, SyntaxError) as ex:
        raise VDFInvalidFileException('invalid vdf file') from ex
    except FileNotFoundError as ex:
        raise VDFFileNotFoundException(f'no such file {path}') from ex


class VDFParserException(Exception):
    pass


class VDFEmptyPathException(VDFParserException):
    pass


class VDFFileNotFoundException(VDFParserException):
    pass


class VDFInvalidFileException(VDFParserException):
    pass
