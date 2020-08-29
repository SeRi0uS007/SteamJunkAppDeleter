import winreg


def get_steam_path() -> str:
    try:
        with winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER) as root_reg:
            with winreg.OpenKey(root_reg, 'SOFTWARE\\Valve\\Steam') as steam_key:
                path = winreg.QueryValueEx(steam_key, 'SteamPath')[0]  # Returns tuple. Only first value interested!
        return path
    except FileNotFoundError as ex:
        raise RegSteamNotFoundException('unable to find Steam installation folder') from ex
    except OSError as ex:
        raise RegConnectException('unable to connect to Windows Registry') from ex


class RegException(Exception):
    pass


class RegConnectException(RegException):
    pass


class RegSteamNotFoundException(RegException):
    pass
