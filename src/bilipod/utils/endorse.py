from typing import Sequence, Union

from bilibili_api import Credential, video


async def endorse(
    endorse_args: Union[str, Sequence, None],
    v_obj: video.Video,
    credential: Credential,
) -> None:
    if endorse_args is None:
        return

    if isinstance(endorse_args, str):
        if endorse_args == "triple":
            await v_obj.triple()
        else:
            raise ValueError("Unsupported endorse method: " + endorse_args)
    elif isinstance(endorse_args, Sequence):
        for endorse_arg in endorse_args:
            if endorse_arg == "like":
                await v_obj.like()
            elif endorse_arg.startswith("coin|"):
                await v_obj.pay_coin(int(endorse_arg.split("|")[1]))
            elif endorse_arg.startswith("favorite|"):
                await v_obj.set_favorite(add_media_id=[int(endorse_arg.split("|")[1])])
            else:
                raise ValueError("Unsupported endorse method: " + endorse_arg)
