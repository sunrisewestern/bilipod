from typing import List, Literal, Optional

from bilibili_api import Credential, user
from bilibili_api.exceptions import ResponseCodeException

from bp_class import Episode, Pod
from utils.bp_log import Logger

logger = Logger().get_logger()


def s2ms(seconds):
    # seconds_to_minute_second
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02}"


async def get_pod_info(
    uid: int,
    page_number: int = 1,
    page_size: int = 5,
    keyword: Optional[str] = None,
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

    if keyword:
        video_list = await user_obj.get_videos(
            pn=page_number, ps=page_size, keyword=keyword, order=user.VideoOrder.PUBDATE
        )
        v_list = video_list["list"]["vlist"]
        episodes_info = [
            {
                "bvid": v["bvid"],
                "title": v["title"],
                "description": v["description"],
                "duration": v["length"],
                "image": v["pic"],
                "pubdate": v["created"],
            }
            for v in v_list
        ]

    else:
        media_list = await user_obj.get_media_list(
            ps=page_size, desc={"desc": True, "asc": False}[playlist_sort]
        )
        v_list = media_list["media_list"]

        episodes_info = [
            {
                "bvid": v["bv_id"],
                "title": v["title"],
                "description": v["intro"],
                "duration": s2ms(v["duration"]),
                "image": v["cover"],
                "pubdate": v["pubtime"],
            }
            for v in v_list
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
            endorse=pod.endorse,
        )
        for episodes_info in pod.episodes
    ]
