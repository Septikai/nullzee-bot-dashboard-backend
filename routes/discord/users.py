import pymongo
from flask import Flask
import requests, time

from helpers import res, cors
import runtime_config
from utils.discord_api import bot_auth_request, fetch_guild_member, fetch_multiple_guild_members


def get_guild_roles():
    return bot_auth_request(f"guilds/{runtime_config.discord_guild_id}/roles", runtime_config.bot_token)


def get_member_colour(common_roles):
    common_roles.reverse()
    filtered = list(filter(lambda d: d["color"] is not None and d["color"] != 0,
                           sorted(common_roles, key=lambda d: d["position"], reverse=True)))
    return filtered[0]


def setup(app: Flask):

    @app.route("/users/<user_id>")
    @cors.site()
    def discord_user(user_id: str):
        if not user_id.isdigit():
            return res.json(code=404)
        print(runtime_config.fetched_members)
        member = fetch_guild_member(user_id)["member"]

        # TODO: implement a check for if the user does not have a db entry
        user_coll_entry = runtime_config.mongodb_user_collection.find_one({"_id": user_id})
        print(user_coll_entry)

        if len(member["roles"]) > 0:
            # Roles
            guild_roles = get_guild_roles()
            guild_role_ids = [r["id"] for r in guild_roles]
            common_role_ids = list(set(guild_role_ids).intersection(member["roles"]))
            common_roles = [role for role in guild_roles if role["id"] in common_role_ids]
            common_roles_dict = {role["id"]: role for role in common_roles}
            member["roles"] = common_roles_dict
            top_colour = get_member_colour(common_roles)["color"]
            member["colour"] = f"{top_colour:x}"
        else:
            member["roles"] = "none"
            member["colour"] = "#FFFFFF"

        print(member)
        print(user_coll_entry)

        return res.json({
            "member_info": member,
            "db_info": user_coll_entry,
        })

    @app.route("/users/<user_id>/punishments")
    @cors.site()
    def user_punishments(user_id: str):
        if not user_id.isdigit():
            return res.json(code=404)

        # TODO: implement a check for if the user does not have a db entry
        user_coll_entry = list(runtime_config.mongodb_moderation_collection.find({"offender_id": int(user_id)}, sort=[("_id", pymongo.DESCENDING)]))
        user_coll_entry = [{key: value for key, value in d.items() if key != "_id"} for d in user_coll_entry]
        for d in user_coll_entry:
            d.update((k, str(v)) for k, v in d.items() if k == "mod_id")

        to_fetch = [p["mod_id"] for p in user_coll_entry]
        mods = fetch_multiple_guild_members(to_fetch)

        for punishment in user_coll_entry:
            if "user" in mods[punishment["mod_id"]]:
                punishment["mod_pfp"] = mods[punishment["mod_id"]]["user"]["avatar"]
                punishment["mod_username"] = f"{mods[punishment['mod_id']]['user']['username']}#" \
                                             f"{mods[punishment['mod_id']]['user']['discriminator']}"
            else:
                punishment["mod_pfp"] = mods[punishment["mod_id"]]["avatar"]
                punishment["mod_username"] = f"{mods[punishment['mod_id']]['username']}#" \
                                             f"{mods[punishment['mod_id']]['discriminator']}"

        print(f"punishments - {user_coll_entry}")

        return res.json({
            "punishments": user_coll_entry
        })

