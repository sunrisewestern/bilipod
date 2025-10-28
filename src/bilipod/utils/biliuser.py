from typing import List, Literal, Optional

from bilibili_api import Credential, channel_series, user

from ..bp_class import Episode, Pod
from .bp_log import Logger

logger = Logger().get_logger()


def s2ms(seconds):
    # seconds_to_minute_second
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02}"


async def get_pod_info(
    uid: int,
    sid: int,
    playlist_type: Literal["season", "series"] = "season",
    page_number: int = 1,
    page_size: int = 5,
    keyword: Optional[str] = None,
    playlist_sort: Literal["desc", "asc"] = "desc",
    credential: Credential = None,
) -> dict:
    if uid:
        return await get_user_info(
            uid=uid,
            page_number=page_number,
            page_size=page_size,
            keyword=keyword,
            playlist_sort=playlist_sort,
            credential=credential,
        )
    else:
        return await get_series_info(
            sid=sid,
            playlist_type=playlist_type,
            page_number=page_number,
            page_size=page_size,
            playlist_sort=playlist_sort,
            credential=credential,
        )


async def get_user_info(
    uid: int,
    page_number: int = 1,
    page_size: int = 5,
    keyword: Optional[str] = None,
    playlist_sort: Literal["desc", "asc"] = "desc",
    credential: Credential = None,
) -> dict:
    user_obj = user.User(uid=uid, credential=credential)

    info = await user_obj.get_user_info()

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
        "title": info.get("name", "Unknown"),
        "description": info.get("sign", ""),
        "cover_art": info.get(
            "face",
            "https://i0.hdslb.com/bfs/archive/c8fd97a40bf79f03e7b76cbc87236f612caef7b2.png",
        ),
        "author": info.get("official", {}).get("title", ""),
        "link": f"https://space.bilibili.com/{uid}",
        "episodes": episodes_info,
    }


async def get_series_info(
    sid: int,
    playlist_type: Literal["season", "series"] = "season",
    page_number: int = 1,
    page_size: int = 5,
    playlist_sort: Literal["desc", "asc"] = "desc",
    credential: Credential = None,
) -> dict:
    # default to get season info
    if playlist_type not in ["season", "series"]:
        raise ValueError(f"Invalid typ {playlist_type}. Must be season or series.")
    
    series = channel_series.ChannelSeries(
        id_=sid,
        type_=channel_series.ChannelSeriesType.SEASON if playlist_type == "season" else channel_series.ChannelSeriesType.SERIES,
        credential=credential,
    )
    info = await series.get_meta()

    video_list = await series.get_videos(
        pn=page_number,
        ps=page_size,
        sort={
            "desc": channel_series.ChannelOrder.DEFAULT,
            "asc": channel_series.ChannelOrder.CHANGE,
        }[playlist_sort],
    )
    v_list = video_list["archives"]
    episodes_info = [
        {
            "bvid": v["bvid"],
            "title": v["title"],
            "description": "",
            "duration": s2ms(v["duration"]),
            "image": v["pic"],
            "pubdate": v["pubdate"],
        }
        for v in v_list
    ]
    
    if playlist_type == "series":
        owner = await series.get_owner()
        owner_info = await owner.get_user_info()
        author = owner_info["name"]
        return {
            "sid": sid,
            "title": info.get("name", "Unknown"),
            "description": info.get("description", ""),
            "cover_art": episodes_info[0]["image"],
            "author": author,
            "link": f"https://space.bilibili.com/{info['mid']}/lists/{sid}?type={playlist_type}",
            "episodes": episodes_info,
        }
    elif playlist_type == "season":
        return {
            "sid": sid,
            "title": info.get("title", "Unknown"),
            "description": info.get("intro", ""),
            "cover_art": info["cover"],
            "author": info["upper"]["name"],
            "link": f"https://space.bilibili.com/{info['mid']}/lists/{sid}?type={playlist_type}",
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
