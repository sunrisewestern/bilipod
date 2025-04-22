import sys
from typing import Literal

from bilibili_api import Credential, Geetest, GeetestType, login_v2, sync, user

from .bp_log import Logger
from .config_parser import BiliPodConfig

logger = Logger().get_logger()


async def password_login(
    choice: Literal["pwd", "sms"],
    username=None,
    password=None,
    phone_number=None,
    country_code="+86",
) -> Credential:
    gee = Geetest()
    await gee.generate_test()
    gee.start_geetest_server()
    print(gee.get_geetest_server_url())
    while not gee.has_done():
        pass
    gee.close_geetest_server()
    print("result:", gee.get_result())

    # Password login
    if choice == "pwd":
        cred = await login_v2.login_with_password(
            username=username, password=password, geetest=gee
        )

    # SMS login
    if choice == "sms":
        phone = login_v2.PhoneNumber(phone_number, country_code)
        captcha_id = await login_v2.send_sms(phonenumber=phone, geetest=gee)
        print("captcha_id:", captcha_id)
        code = input("code: ")
        cred = await login_v2.login_with_sms(
            phonenumber=phone, code=code, captcha_id=captcha_id
        )

    # Security verification
    if isinstance(cred, login_v2.LoginCheck):
        gee = Geetest()
        await gee.generate_test(type_=GeetestType.VERIFY)
        gee.start_geetest_server()
        print(gee.get_geetest_server_url())
        while not gee.has_done():
            pass
        gee.close_geetest_server()
        print("result:", gee.get_result())
        await cred.send_sms(gee)
        code = input("code:")
        cred = await cred.complete_check(code)

    print("cookies:", cred.get_cookies())
    return cred


async def get_credential(config: BiliPodConfig) -> Credential:
    if (
        config.token.bili_jct
        and config.token.buvid3
        and config.token.dedeuserid
        and config.token.sessdata
    ):
        if not config.token.ac_time_value:
            logger.warning("ac_time_value is not set. It may cause some issues.")

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
            logger.error(
                "Login failed. Credential is not valid. Please check your token."
            )
            sys.exit()
    else:
        if config.login.username and config.login.password:
            # Password login
            credential = await password_login(
                choice="pwd",
                username=config.login.username,
                password=config.login.password,
            )
        elif config.login.phone_number:
            # SMS login
            credential = await password_login(
                choice="sms",
                phone_number=config.login.phone_number,
                country_code=config.login.country_code,
            )
        else:
            choice = input("Please choose login method (pwd/sms): ")
            if choice == "pwd":
                username = input("Username: ")
                password = input("Password: ")
                credential = await password_login(
                    choice="pwd", username=username, password=password
                )
            elif choice == "sms":
                phone_number = input("Phone number: ")
                country_code = input("Country code (default +86): ") or "+86"
                credential = await password_login(
                    choice="sms",
                    phone_number=phone_number,
                    country_code=country_code,
                )
            else:
                logger.error("Invalid choice. Please choose either 'pwd' or 'sms'.")
                sys.exit()

        logger.debug(
            f"""
                bili_jct: {credential.bili_jct}
                buvid3: {credential.buvid3}
                dedeuserid: {credential.dedeuserid}
                sessdata: {credential.sessdata}
                ac_time_value: {credential.ac_time_value}
            """
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
