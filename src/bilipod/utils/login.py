import sys

from bilibili_api import Credential, ResponseCodeException, login, user

from .bp_log import Logger
from .config_parser import BiliPodConfig

logger = Logger().get_logger()


def qrcode_login(terminal: bool = True) -> Credential:
    logger.info("Login：")
    if terminal:
        credential = login.login_with_qrcode_term()
    else:
        credential = login.login_with_qrcode()

    try:
        credential.raise_for_no_bili_jct()
        credential.raise_for_no_sessdata()
    except ResponseCodeException as e:  # noqa E722
        logger.error(f"Login failed. Error: {e}")
        sys.exit()
    return credential


async def get_credential(config: BiliPodConfig) -> Credential:
    if config.token.bili_jct:
        credential = Credential(
            bili_jct=config.token.bili_jct,
            buvid3=config.token.buvid3,
            # buvid4=config.token.buvid4,
            dedeuserid=config.token.dedeuserid,
            sessdata=config.token.sessdata,
            ac_time_value=config.token.ac_time_value,
        )
        # check valid
        validation = await credential.check_valid()
        if not validation:
            logger.error("Login failed. Credential is not valid. Please check your token.")
            sys.exit()
    else:
        credential = qrcode_login()
        print(
            credential.ac_time_value,
            credential.bili_jct,
            credential.buvid3,
            credential.dedeuserid,
            credential.sessdata,
        )

    user_info = await user.get_self_info(credential)
    logger.info(f"Welcome, {user_info['name']}!")

    return credential


async def update_credential(credential: Credential):
    validation = await credential.check_valid()
    if not validation:
        logger.error("Credential is outdated. Please check your token.")
        sys.exit()

    update_status = await credential.check_refresh()
    if update_status:
        logger.debug("Updating token...")
        try:
            await credential.refresh()
        except Exception as e:
            logger.error(f"Failed to update token: {e}")
            sys.exit()

    else:
        logger.debug("No need to update token")
