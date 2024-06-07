from typing import List, Literal

from bilibili_api import Credential, user
from bilibili_api.exceptions import ResponseCodeException

from bp_class import Episode, Pod
from utils.bp_log import Logger

logger = Logger().get_logger()


async def get_pod_info(
    uid: int,
    page_number: int = 1,
    page_size: int = 5,
    keyword: str = "",
    playlist_sort: Literal["desc", "asc"] = "desc",
    credential: Credential = None,
) -> dict:
    try:
        user_obj = user.User(uid=uid, credential=credential)
    except ResponseCodeException as e:
        logger.error(e)
        raise e

    info = await user_obj.get_user_info()
    # logger.debug(info)

    v_list = await user_obj.get_videos(
        pn=page_number, ps=page_size, keyword=keyword, order=user.VideoOrder.PUBDATE
    )

    episodes_info = [
        {
            "bvid": v["bvid"],
            "title": v["title"],
            "description": v["description"],
            "duration": v["length"],
            "image": v["pic"],
            "pubdate": v["created"],
        }
        for v in v_list["list"]["vlist"]
    ]

    return {
        "uid": uid,
        "title": info["name"],
        "description": info["sign"],
        "cover_art": info["face"],
        "author": info["official"].get("title", ""),
        "link": f"https://space.bilibili.com/{uid}",
        "episodes": episodes_info,
    }


def get_episode_list(pod: Pod) -> List[Episode]:
    return [
        Episode(
            **episodes_info,
            format=pod.format,
            quality=pod.quality,
            data_dir=pod.data_dir,
            base_url=pod.base_url,
        )
        for episodes_info in pod.episodes
    ]
