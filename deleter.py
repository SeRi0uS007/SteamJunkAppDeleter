# Version 1.0.0
import internal_sublib.web_helper.webauth as webauth
import internal_sublib.sys_helper.steam_registry as steam_registry
from internal_sublib.sys_helper.vdf_parser import get_hidden_apps

import asyncio
import re
import json
import logging

MAX_WORKERS = 5


async def remove_app(web: webauth.Web, queue: asyncio.Queue):
    while True:
        appid = 0
        # noinspection PyBroadException
        try:
            appid = await queue.get()
            sessionid = web.sessionid

            help_game_raw = await web.get(
                f'https://help.steampowered.com/ru/wizard/HelpWithGame/?appid={appid}&'
                f'sessionid={sessionid}&wizard_ajax=1')
            response = json.loads(help_game_raw)

            advanced_help_uri = re.search(r'https://help\.steampowered\.com/ru/wizard/HelpWithGameIssue/\?appid=\d*&'
                                          r'issueid=123&transid=\d*&line_item=\d*', response['html'])

            if not advanced_help_uri:  # game entry doesn't have transid and line_item
                advanced_help_uri = f'https://help.steampowered.com/ru/wizard/HelpWithGameIssue/?appid={appid}' \
                                    f'&issueid=123'
            else:
                advanced_help_uri = advanced_help_uri.group(0)

            advanced_help_raw = await web.get(f'{advanced_help_uri}&sessionid={sessionid}&wizard_ajax=1')
            response = json.loads(advanced_help_raw)

            chosen_packages = re.findall(r'https://help\.steampowered\.com/ru/wizard/HelpWithGameIssue/\?appid=\d*&'
                                         r'issueid=123&chosenpackage=\d*', response['html'])
            packages = []
            if chosen_packages:
                for chosen_package in chosen_packages:
                    chosen_raw = await web.get(f'{chosen_package}&sessionid={sessionid}&wizard_ajax=1')
                    response = json.loads(chosen_raw)
                    packages.append(
                        re.search(r'<input name=\"packageid\".*value=\"(\d*)\">', response['html']).group(1)
                    )
            else:
                packages.append(
                    re.search(r'<input name=\"packageid\".*value=\"(\d*)\">', response['html']).group(1)
                )

            for package_id in packages:
                delete_game_raw = await web.post('https://help.steampowered.com/ru/wizard/AjaxDoPackageRemove', {
                    'packageid': package_id,
                    'appid': str(appid),
                    'sessionid': sessionid,
                    'wizard_ajax': '1'
                })
                response = json.loads(delete_game_raw)

                if response['success']:
                    await asyncio.sleep(3)
                else:
                    raise Exception('Unsuccessful deletion')
            queue.task_done()
            logging.info(f'AppID: {appid} is removed')
        except asyncio.CancelledError as _:
            break
        except Exception as ex:
            logging.error(f'An exception occurred while removing the app ({appid}): {ex!s}', exc_info=True)
            queue.task_done()


async def main():
    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)

    try:
        steam_folder = steam_registry.get_steam_path()
    except steam_registry.RegSteamNotFoundException as ex:
        logging.critical(f'Can\'t find Steam folder {ex!s}', exc_info=True)
        return

    logging.info(f'Found Steam folder at: {steam_folder}')

    login = ''
    while not login:
        login = input('Enter your Steam Username: ')

    password = ''
    while not password:
        password = input('Enter your Steam Password: ')

    steam_web = webauth.Web(login, password)

    logging.info(f'Login to Steam as {login}')

    need_two_factor = False
    need_email_code = False
    try:
        await steam_web.login()
    except webauth.TwoFactorCodeRequired:
        need_two_factor = True
        logging.warning('Two factor code needed')
    except webauth.EmailCodeRequired:
        need_email_code = True
        logging.warning('Email code needed')

    if need_two_factor:
        try:
            two_factor = ''
            while not two_factor:
                two_factor = input('Enter your Steam Two Factor Code: ')
            await steam_web.login(two_factor=two_factor)
        except Exception as ex:
            logging.critical(f'Exception during login: {ex!s}', exc_info=True)
            await steam_web.free()
            return
    elif need_email_code:
        try:
            email_code = ''
            while not email_code:
                email_code = input('Enter your Steam Email Code: ')
            await steam_web.login(email_code=email_code)
        except Exception as ex:
            logging.critical(f'Exception during login: {ex!s}', exc_info=True)
            await steam_web.free()
            return

    logging.info('Login: Done')

    vdf_path = f'{steam_folder}/userdata/{steam_web.steamid.accountid}/7/remote/sharedconfig.vdf'
    logging.info(f'Search hidden apps in "{vdf_path}" file')
    # noinspection PyBroadException
    try:
        apps = get_hidden_apps(vdf_path)
    except Exception as ex:
        logging.critical(f'Exception during parsing vdf file: {ex!s}')
        await steam_web.free()
        return

    if not apps:
        logging.critical('There is no hidden apps')
        await steam_web.free()
        return

    logging.info(f'Found {len(apps)} of hidden apps')

    queue = asyncio.Queue()
    for app in apps:
        queue.put_nowait(app)

    logging.info(f'Initiating a {MAX_WORKERS}\'s workers')
    tasks = []
    for _ in range(MAX_WORKERS):
        task = asyncio.create_task(remove_app(steam_web, queue))
        tasks.append(task)

    await queue.join()

    for task in tasks:
        task.cancel()

    await asyncio.gather(*tasks)

    await steam_web.free()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
