from typing import Union

from tinydb import Query

from ..bp_class import Episode


def query_episode(episode: Union[Episode, dict]) -> Query:
    if isinstance(episode, dict):
        return (
            (Query().bvid == episode["bvid"])
            & (Query().quality == episode["quality"])
            & (Query().format == episode["format"])
        )
    elif isinstance(episode, Episode):
        return (
            (Query().bvid == episode.bvid)
            & (Query().quality == episode.quality)
            & (Query().format == episode.format)
        )
    else:
        raise TypeError("Invalid type for episode query")
