-- ZATHROTH SQLite database schema

-- Table structure `server_config`
CREATE TABLE IF NOT EXISTS `server_config` (
    `config` TEXT NOT NULL,
    `value` TEXT NOT NULL DEFAULT '',
    CONSTRAINT `server_config_pk` PRIMARY KEY (`config`)
);

INSERT INTO `server_config` (`config`, `value`) VALUES ('db_version', '59'), ('motd_hash', ''), ('motd_num', '0'), ('players_record', '0');

-- Table structure `accounts`
CREATE TABLE IF NOT EXISTS `accounts` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `name` TEXT COLLATE NOCASE NOT NULL,
    `password` TEXT NOT NULL,
    `email` TEXT COLLATE NOCASE NOT NULL DEFAULT '',
    `premdays` INTEGER NOT NULL DEFAULT 0,
    `premdays_purchased` INTEGER NOT NULL DEFAULT 0,
    `lastday` INTEGER NOT NULL DEFAULT 0,
    `type` INTEGER NOT NULL DEFAULT 1,
    `coins` INTEGER NOT NULL DEFAULT 0,
    `coins_transferable` INTEGER NOT NULL DEFAULT 0,
    `tournament_coins` INTEGER NOT NULL DEFAULT 0,
    `creation` INTEGER NOT NULL DEFAULT 0,
    `recruiter` INTEGER DEFAULT 0,
    `house_bid_id` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `accounts_unique` UNIQUE (`name`)
);
CREATE INDEX IF NOT EXISTS `accounts_email_idx` ON `accounts` (`email`);
CREATE INDEX IF NOT EXISTS `accounts_password_idx` ON `accounts` (`password`);

-- Table structure `coins_transactions`
CREATE TABLE IF NOT EXISTS `coins_transactions` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `account_id` INTEGER NOT NULL,
    `type` INTEGER NOT NULL,
    `coin_type` INTEGER NOT NULL DEFAULT 1,
    `amount` INTEGER NOT NULL,
    `description` TEXT NOT NULL,
    `timestamp` TEXT DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `coins_transactions_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `coins_transactions_account_id_idx` ON `coins_transactions` (`account_id`);

-- Table structure `players`
CREATE TABLE IF NOT EXISTS `players` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `name` TEXT COLLATE NOCASE NOT NULL,
    `group_id` INTEGER NOT NULL DEFAULT 1,
    `account_id` INTEGER NOT NULL DEFAULT 0,
    `level` INTEGER NOT NULL DEFAULT 1,
    `vocation` INTEGER NOT NULL DEFAULT 0,
    `health` INTEGER NOT NULL DEFAULT 150,
    `healthmax` INTEGER NOT NULL DEFAULT 150,
    `experience` INTEGER NOT NULL DEFAULT 0,
    `lookbody` INTEGER NOT NULL DEFAULT 0,
    `lookfeet` INTEGER NOT NULL DEFAULT 0,
    `lookhead` INTEGER NOT NULL DEFAULT 0,
    `looklegs` INTEGER NOT NULL DEFAULT 0,
    `looktype` INTEGER NOT NULL DEFAULT 136,
    `lookaddons` INTEGER NOT NULL DEFAULT 0,
    `maglevel` INTEGER NOT NULL DEFAULT 0,
    `mana` INTEGER NOT NULL DEFAULT 0,
    `manamax` INTEGER NOT NULL DEFAULT 0,
    `manaspent` INTEGER NOT NULL DEFAULT 0,
    `soul` INTEGER NOT NULL DEFAULT 0,
    `town_id` INTEGER NOT NULL DEFAULT 1,
    `posx` INTEGER NOT NULL DEFAULT 0,
    `posy` INTEGER NOT NULL DEFAULT 0,
    `posz` INTEGER NOT NULL DEFAULT 0,
    `conditions` BLOB NOT NULL DEFAULT X'',
    `cap` INTEGER NOT NULL DEFAULT 0,
    `sex` INTEGER NOT NULL DEFAULT 0,
    `pronoun` INTEGER NOT NULL DEFAULT 0,
    `lastlogin` INTEGER NOT NULL DEFAULT 0,
    `lastip` INTEGER NOT NULL DEFAULT 0,
    `save` INTEGER NOT NULL DEFAULT 1,
    `skull` INTEGER NOT NULL DEFAULT 0,
    `skulltime` INTEGER NOT NULL DEFAULT 0,
    `expert_pvp_mode` INTEGER NOT NULL DEFAULT 0,
    `lastlogout` INTEGER NOT NULL DEFAULT 0,
    `blessings` INTEGER NOT NULL DEFAULT 0,
    `blessings1` INTEGER NOT NULL DEFAULT 0,
    `blessings2` INTEGER NOT NULL DEFAULT 0,
    `blessings3` INTEGER NOT NULL DEFAULT 0,
    `blessings4` INTEGER NOT NULL DEFAULT 0,
    `blessings5` INTEGER NOT NULL DEFAULT 0,
    `blessings6` INTEGER NOT NULL DEFAULT 0,
    `blessings7` INTEGER NOT NULL DEFAULT 0,
    `blessings8` INTEGER NOT NULL DEFAULT 0,
    `onlinetime` INTEGER NOT NULL DEFAULT 0,
    `deletion` INTEGER NOT NULL DEFAULT 0,
    `balance` INTEGER NOT NULL DEFAULT 0,
    `offlinetraining_time` INTEGER NOT NULL DEFAULT 43200,
    `offlinetraining_skill` INTEGER NOT NULL DEFAULT -1,
    `stamina` INTEGER NOT NULL DEFAULT 2520,
    `skill_fist` INTEGER NOT NULL DEFAULT 10,
    `skill_fist_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_club` INTEGER NOT NULL DEFAULT 10,
    `skill_club_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_sword` INTEGER NOT NULL DEFAULT 10,
    `skill_sword_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_axe` INTEGER NOT NULL DEFAULT 10,
    `skill_axe_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_dist` INTEGER NOT NULL DEFAULT 10,
    `skill_dist_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_shielding` INTEGER NOT NULL DEFAULT 10,
    `skill_shielding_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_fishing` INTEGER NOT NULL DEFAULT 10,
    `skill_fishing_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_critical_hit_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_critical_hit_chance_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_critical_hit_damage` INTEGER NOT NULL DEFAULT 0,
    `skill_critical_hit_damage_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_life_leech_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_life_leech_chance_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_life_leech_amount` INTEGER NOT NULL DEFAULT 0,
    `skill_life_leech_amount_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_mana_leech_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_mana_leech_chance_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_mana_leech_amount` INTEGER NOT NULL DEFAULT 0,
    `skill_mana_leech_amount_tries` INTEGER NOT NULL DEFAULT 0,
    `skill_criticalhit_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_criticalhit_damage` INTEGER NOT NULL DEFAULT 0,
    `skill_lifeleech_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_lifeleech_amount` INTEGER NOT NULL DEFAULT 0,
    `skill_manaleech_chance` INTEGER NOT NULL DEFAULT 0,
    `skill_manaleech_amount` INTEGER NOT NULL DEFAULT 0,
    `manashield` INTEGER NOT NULL DEFAULT 0,
    `max_manashield` INTEGER NOT NULL DEFAULT 0,
    `xpboost_stamina` INTEGER DEFAULT NULL,
    `xpboost_value` INTEGER DEFAULT NULL,
    `marriage_status` INTEGER NOT NULL DEFAULT 0,
    `marriage_spouse` INTEGER NOT NULL DEFAULT -1,
    `bonus_rerolls` INTEGER NOT NULL DEFAULT 0,
    `prey_wildcard` INTEGER NOT NULL DEFAULT 0,
    `task_points` INTEGER NOT NULL DEFAULT 0,
    `quickloot_fallback` INTEGER DEFAULT 0,
    `lookmountbody` INTEGER NOT NULL DEFAULT 0,
    `lookmountfeet` INTEGER NOT NULL DEFAULT 0,
    `lookmounthead` INTEGER NOT NULL DEFAULT 0,
    `lookmountlegs` INTEGER NOT NULL DEFAULT 0,
    `lookfamiliarstype` INTEGER NOT NULL DEFAULT 0,
    `isreward` INTEGER NOT NULL DEFAULT 1,
    `istutorial` INTEGER NOT NULL DEFAULT 0,
    `forge_dusts` INTEGER NOT NULL DEFAULT 0,
    `forge_dust_level` INTEGER NOT NULL DEFAULT 100,
    `randomize_mount` INTEGER NOT NULL DEFAULT 0,
    `boss_points` INTEGER NOT NULL DEFAULT 0,
    `comment` TEXT NOT NULL DEFAULT '',
    `animus_mastery` BLOB DEFAULT NULL,
    CONSTRAINT `players_unique` UNIQUE (`name`),
    CONSTRAINT `players_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `players_account_id_idx` ON `players` (`account_id`);
CREATE INDEX IF NOT EXISTS `players_vocation_idx` ON `players` (`vocation`);

-- Table structure `account_bans`
CREATE TABLE IF NOT EXISTS `account_bans` (
    `account_id` INTEGER NOT NULL,
    `reason` TEXT NOT NULL,
    `banned_at` INTEGER NOT NULL,
    `expires_at` INTEGER NOT NULL,
    `banned_by` INTEGER NOT NULL,
    CONSTRAINT `account_bans_pk` PRIMARY KEY (`account_id`),
    CONSTRAINT `account_bans_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
    CONSTRAINT `account_bans_player_fk`
    FOREIGN KEY (`banned_by`) REFERENCES `players` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS `account_bans_banned_by_idx` ON `account_bans` (`banned_by`);

-- Table structure `account_ban_history`
CREATE TABLE IF NOT EXISTS `account_ban_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `account_id` INTEGER NOT NULL,
    `reason` TEXT NOT NULL,
    `banned_at` INTEGER NOT NULL,
    `expired_at` INTEGER NOT NULL,
    `banned_by` INTEGER NOT NULL,
    CONSTRAINT `account_bans_history_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
    CONSTRAINT `account_bans_history_player_fk`
    FOREIGN KEY (`banned_by`) REFERENCES `players` (`id`)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS `account_ban_history_account_id_idx` ON `account_ban_history` (`account_id`);
CREATE INDEX IF NOT EXISTS `account_ban_history_banned_by_idx` ON `account_ban_history` (`banned_by`);

-- Table structure `account_viplist`
CREATE TABLE IF NOT EXISTS `account_viplist` (
    `account_id` INTEGER NOT NULL,
    `player_id` INTEGER NOT NULL,
    `description` TEXT NOT NULL DEFAULT '',
    `icon` INTEGER NOT NULL DEFAULT 0,
    `notify` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `account_viplist_unique` UNIQUE (`account_id`, `player_id`),
    CONSTRAINT `account_viplist_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE,
    CONSTRAINT `account_viplist_player_fk`
    FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `account_viplist_account_id_idx` ON `account_viplist` (`account_id`);
CREATE INDEX IF NOT EXISTS `account_viplist_player_id_idx` ON `account_viplist` (`player_id`);

-- Table structure `account_vipgroup`
CREATE TABLE IF NOT EXISTS `account_vipgroups` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `account_id` INTEGER NOT NULL,
    `name` TEXT NOT NULL,
    `customizable` INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT `account_vipgroups_pk` UNIQUE (`id`, `account_id`),
    CONSTRAINT `account_vipgroups_accounts_fk`
        FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
        ON DELETE CASCADE
);

--
-- Trigger
--
CREATE TRIGGER `oncreate_accounts` AFTER INSERT ON `accounts` FOR EACH ROW BEGIN
    INSERT INTO `account_vipgroups` (`account_id`, `name`, `customizable`) VALUES (NEW.`id`, 'Enemies', 0);
    INSERT INTO `account_vipgroups` (`account_id`, `name`, `customizable`) VALUES (NEW.`id`, 'Friends', 0);
    INSERT INTO `account_vipgroups` (`account_id`, `name`, `customizable`) VALUES (NEW.`id`, 'Trading Partner', 0);
END;

-- Table structure `account_vipgrouplist`
CREATE TABLE IF NOT EXISTS `account_vipgrouplist` (
    `account_id` INTEGER NOT NULL,
    `player_id` INTEGER NOT NULL,
    `vipgroup_id` INTEGER NOT NULL,
    CONSTRAINT `account_vipgrouplist_unique` UNIQUE (`account_id`, `player_id`, `vipgroup_id`),
    CONSTRAINT `account_vipgrouplist_player_fk`
    FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
    ON DELETE CASCADE,
    CONSTRAINT `account_vipgrouplist_vipgroup_fk`
    FOREIGN KEY (`vipgroup_id`, `account_id`) REFERENCES `account_vipgroups` (`id`, `account_id`)
    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `account_vipgrouplist_account_id_idx` ON `account_vipgrouplist` (`account_id`);
CREATE INDEX IF NOT EXISTS `account_vipgrouplist_player_id_idx` ON `account_vipgrouplist` (`player_id`);
CREATE INDEX IF NOT EXISTS `account_vipgrouplist_vipgroup_id_idx` ON `account_vipgrouplist` (`vipgroup_id`);

-- Table structure `boosted_boss`
CREATE TABLE IF NOT EXISTS `boosted_boss` (
    `boostname` TEXT,
    `date` TEXT NOT NULL DEFAULT '',
    `raceid` TEXT NOT NULL DEFAULT '',
    `looktypeEx` INTEGER NOT NULL DEFAULT 0,
    `looktype` INTEGER NOT NULL DEFAULT 136,
    `lookfeet` INTEGER NOT NULL DEFAULT 0,
    `looklegs` INTEGER NOT NULL DEFAULT 0,
    `lookhead` INTEGER NOT NULL DEFAULT 0,
    `lookbody` INTEGER NOT NULL DEFAULT 0,
    `lookaddons` INTEGER NOT NULL DEFAULT 0,
    `lookmount` INTEGER DEFAULT 0,
    PRIMARY KEY (`date`)
);

INSERT INTO `boosted_boss` (`boostname`, `date`, `raceid`) VALUES ('default', 0, 0);

-- Table structure `boosted_creature`
CREATE TABLE IF NOT EXISTS `boosted_creature` (
    `boostname` TEXT,
    `date` TEXT NOT NULL DEFAULT '',
    `raceid` TEXT NOT NULL DEFAULT '',
    `looktype` INTEGER NOT NULL DEFAULT 136,
    `lookfeet` INTEGER NOT NULL DEFAULT 0,
    `looklegs` INTEGER NOT NULL DEFAULT 0,
    `lookhead` INTEGER NOT NULL DEFAULT 0,
    `lookbody` INTEGER NOT NULL DEFAULT 0,
    `lookaddons` INTEGER NOT NULL DEFAULT 0,
    `lookmount` INTEGER DEFAULT 0,
    PRIMARY KEY (`date`)
);

INSERT INTO `boosted_creature` (`boostname`, `date`, `raceid`) VALUES ('default', 0, 0);

-- Tabble Structure `daily_reward_history`
CREATE TABLE IF NOT EXISTS `daily_reward_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `daystreak` INTEGER NOT NULL DEFAULT 0,
    `player_id` INTEGER NOT NULL,
    `timestamp` INTEGER NOT NULL,
    `description` TEXT DEFAULT NULL,
    CONSTRAINT `daily_reward_history_player_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `daily_reward_history_player_id_idx` ON `daily_reward_history` (`player_id`);

-- Tabble Structure `forge_history`
CREATE TABLE IF NOT EXISTS `forge_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `player_id` INTEGER NOT NULL,
    `action_type` INTEGER NOT NULL DEFAULT 0,
    `description` TEXT NOT NULL,
    `is_success` INTEGER NOT NULL DEFAULT 0,
    `bonus` INTEGER NOT NULL DEFAULT 0,
    `done_at` INTEGER NOT NULL,
    `done_at_date` TEXT DEFAULT CURRENT_TIMESTAMP,
    `cost` INTEGER NOT NULL DEFAULT 0,
    `gained` INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (`player_id`) REFERENCES `players` (`id`) ON DELETE CASCADE,
    CONSTRAINT `unique_player_done_at` UNIQUE (`player_id`, `done_at`)
);

-- Table structure `global_storage`
CREATE TABLE IF NOT EXISTS `global_storage` (
    `key` TEXT NOT NULL,
    `value` TEXT NOT NULL,
    CONSTRAINT `global_storage_unique` UNIQUE (`key`)
);

-- Table structure `guilds`
CREATE TABLE IF NOT EXISTS `guilds` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `level` INTEGER NOT NULL DEFAULT 1,
    `name` TEXT COLLATE NOCASE NOT NULL,
    `ownerid` INTEGER NOT NULL,
    `creationdata` INTEGER NOT NULL,
    `motd` TEXT NOT NULL DEFAULT '',
    `residence` INTEGER NOT NULL DEFAULT 0,
    `balance` INTEGER NOT NULL DEFAULT 0,
    `points` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `guilds_name_unique` UNIQUE (`name`),
    CONSTRAINT `guilds_owner_unique` UNIQUE (`ownerid`),
    CONSTRAINT `guilds_ownerid_fk`
        FOREIGN KEY (`ownerid`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `guild_wars`
CREATE TABLE IF NOT EXISTS `guild_wars` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `guild1` INTEGER NOT NULL DEFAULT 0,
    `guild2` INTEGER NOT NULL DEFAULT 0,
    `name1` TEXT NOT NULL,
    `name2` TEXT NOT NULL,
    `status` INTEGER NOT NULL DEFAULT 0,
    `started` INTEGER NOT NULL DEFAULT 0,
    `ended` INTEGER NOT NULL DEFAULT 0,
    `frags_limit` INTEGER NOT NULL DEFAULT 0,
    `payment` INTEGER NOT NULL DEFAULT 0,
    `duration_days` INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS `guild_wars_guild1_idx` ON `guild_wars` (`guild1`);
CREATE INDEX IF NOT EXISTS `guild_wars_guild2_idx` ON `guild_wars` (`guild2`);

-- Table structure `guildwar_kills`
CREATE TABLE IF NOT EXISTS `guildwar_kills` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `killer` TEXT NOT NULL,
    `target` TEXT NOT NULL,
    `killerguild` INTEGER NOT NULL DEFAULT 0,
    `targetguild` INTEGER NOT NULL DEFAULT 0,
    `warid` INTEGER NOT NULL DEFAULT 0,
    `time` INTEGER NOT NULL,
    CONSTRAINT `guildwar_kills_warid_fk`
        FOREIGN KEY (`warid`) REFERENCES `guild_wars` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `guildwar_kills_warid_idx` ON `guildwar_kills` (`warid`);

-- Table structure `guild_invites`
CREATE TABLE IF NOT EXISTS `guild_invites` (
    `player_id` INTEGER NOT NULL DEFAULT 0,
    `guild_id` INTEGER NOT NULL DEFAULT 0,
    `date` INTEGER NOT NULL,
    CONSTRAINT `guild_invites_pk` PRIMARY KEY (`player_id`, `guild_id`),
    CONSTRAINT `guild_invites_player_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `guild_invites_guild_fk`
        FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `guild_invites_guild_id_idx` ON `guild_invites` (`guild_id`);

-- Table structure `guild_ranks`
CREATE TABLE IF NOT EXISTS `guild_ranks` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `guild_id` INTEGER NOT NULL,
    `name` TEXT COLLATE NOCASE NOT NULL,
    `level` INTEGER NOT NULL,
    CONSTRAINT `guild_ranks_fk`
        FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `guild_ranks_guild_id_idx` ON `guild_ranks` (`guild_id`);

--
-- Trigger
--
CREATE TRIGGER `oncreate_guilds` AFTER INSERT ON `guilds` FOR EACH ROW BEGIN
    INSERT INTO `guild_ranks` (`name`, `level`, `guild_id`) VALUES ('The Leader', 3, NEW.`id`);
    INSERT INTO `guild_ranks` (`name`, `level`, `guild_id`) VALUES ('Vice-Leader', 2, NEW.`id`);
    INSERT INTO `guild_ranks` (`name`, `level`, `guild_id`) VALUES ('Member', 1, NEW.`id`);
END;

-- Table structure `guild_membership`
CREATE TABLE IF NOT EXISTS `guild_membership` (
    `player_id` INTEGER NOT NULL,
    `guild_id` INTEGER NOT NULL,
    `rank_id` INTEGER NOT NULL,
    `nick` TEXT NOT NULL DEFAULT '',
    CONSTRAINT `guild_membership_pk` PRIMARY KEY (`player_id`),
    CONSTRAINT `guild_membership_player_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `guild_membership_guild_fk`
        FOREIGN KEY (`guild_id`) REFERENCES `guilds` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `guild_membership_rank_fk`
        FOREIGN KEY (`rank_id`) REFERENCES `guild_ranks` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS `guild_membership_guild_id_idx` ON `guild_membership` (`guild_id`);
CREATE INDEX IF NOT EXISTS `guild_membership_rank_id_idx` ON `guild_membership` (`rank_id`);

-- Table structure `houses`
CREATE TABLE IF NOT EXISTS `houses` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `owner` INTEGER NOT NULL,
    `new_owner` INTEGER NOT NULL DEFAULT -1,
    `paid` INTEGER NOT NULL DEFAULT 0,
    `warnings` INTEGER NOT NULL DEFAULT 0,
    `name` TEXT NOT NULL,
    `rent` INTEGER NOT NULL DEFAULT 0,
    `town_id` INTEGER NOT NULL DEFAULT 0,
    `size` INTEGER NOT NULL DEFAULT 0,
    `guildid` INTEGER,
    `beds` INTEGER NOT NULL DEFAULT 0,
    `bidder` INTEGER NOT NULL DEFAULT 0,
    `bidder_name` TEXT NOT NULL DEFAULT '',
    `highest_bid` INTEGER NOT NULL DEFAULT 0,
    `internal_bid` INTEGER NOT NULL DEFAULT 0,
    `bid_end_date` INTEGER NOT NULL DEFAULT 0,
    `state` INTEGER NOT NULL DEFAULT 0,
    `transfer_status` INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS `houses_owner_idx` ON `houses` (`owner`);
CREATE INDEX IF NOT EXISTS `houses_town_id_idx` ON `houses` (`town_id`);

--
-- trigger
--
CREATE TRIGGER `ondelete_players` BEFORE DELETE ON `players` FOR EACH ROW BEGIN
    UPDATE `houses` SET `owner` = 0 WHERE `owner` = OLD.`id`;
END;

-- Table structure `house_lists`
CREATE TABLE IF NOT EXISTS `house_lists` (
    `house_id` INTEGER NOT NULL,
    `listid` INTEGER NOT NULL,
    `version` INTEGER NOT NULL DEFAULT 0,
    `list` TEXT NOT NULL,
    PRIMARY KEY (`house_id`, `listid`),
    CONSTRAINT `houses_list_house_fk` FOREIGN KEY (`house_id`) REFERENCES `houses` (`id`) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `house_lists_house_id_index_idx` ON `house_lists` (`house_id`);
CREATE INDEX IF NOT EXISTS `house_lists_version_idx` ON `house_lists` (`version`);

-- Table structure `ip_bans`
CREATE TABLE IF NOT EXISTS `ip_bans` (
    `ip` INTEGER NOT NULL,
    `reason` TEXT NOT NULL,
    `banned_at` INTEGER NOT NULL,
    `expires_at` INTEGER NOT NULL,
    `banned_by` INTEGER NOT NULL,
    CONSTRAINT `ip_bans_pk` PRIMARY KEY (`ip`),
    CONSTRAINT `ip_bans_players_fk`
        FOREIGN KEY (`banned_by`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS `ip_bans_banned_by_idx` ON `ip_bans` (`banned_by`);

-- Table structure `market_history`
CREATE TABLE IF NOT EXISTS `market_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `player_id` INTEGER NOT NULL,
    `sale` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL,
    `amount` INTEGER NOT NULL,
    `price` INTEGER NOT NULL DEFAULT 0,
    `expires_at` INTEGER NOT NULL,
    `inserted` INTEGER NOT NULL,
    `state` INTEGER NOT NULL,
    `tier` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `market_history_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `market_history_player_id_idx` ON `market_history` (`player_id`,`sale`);

-- Table structure `market_offers`
CREATE TABLE IF NOT EXISTS `market_offers` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `player_id` INTEGER NOT NULL,
    `sale` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL,
    `amount` INTEGER NOT NULL,
    `created` INTEGER NOT NULL,
    `anonymous` INTEGER NOT NULL DEFAULT 0,
    `price` INTEGER NOT NULL DEFAULT 0,
    `tier` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `market_offers_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `market_offers_sale_idx` ON `market_offers` (`sale`,`itemtype`);
CREATE INDEX IF NOT EXISTS `market_offers_created_idx` ON `market_offers` (`created`);
CREATE INDEX IF NOT EXISTS `market_offers_player_id_idx` ON `market_offers` (`player_id`);

-- Table structure `players_online`
CREATE TABLE IF NOT EXISTS `players_online` (
    `player_id` INTEGER NOT NULL,
    CONSTRAINT `players_online_pk` PRIMARY KEY (`player_id`),
    CONSTRAINT `players_online_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `active_livestream_casters`
CREATE TABLE IF NOT EXISTS `active_livestream_casters` (
    `caster_id` INTEGER NOT NULL,
    `livestream_status` INTEGER NOT NULL DEFAULT 0,
    `livestream_viewers` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `active_livestream_casters_pk` PRIMARY KEY (`caster_id`),
    CONSTRAINT `active_livestream_casters_players_fk`
        FOREIGN KEY (`caster_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_charm`
CREATE TABLE IF NOT EXISTS `player_charms` (
    `player_id` INTEGER NOT NULL,
    `charm_points` INTEGER NOT NULL DEFAULT 0,
    `minor_charm_echoes` INTEGER NOT NULL DEFAULT 0,
    `max_charm_points` INTEGER NOT NULL DEFAULT 0,
    `max_minor_charm_echoes` INTEGER NOT NULL DEFAULT 0,
    `charm_expansion` INTEGER NOT NULL DEFAULT FALSE,
    `UsedRunesBit` INTEGER NOT NULL DEFAULT 0,
    `UnlockedRunesBit` INTEGER NOT NULL DEFAULT 0,
    `charms` BLOB NULL,
    `tracker list` BLOB NULL,
    CONSTRAINT `player_charms_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_deaths`
CREATE TABLE IF NOT EXISTS `player_deaths` (
    `player_id` INTEGER NOT NULL,
    `time` INTEGER NOT NULL DEFAULT 0,
    `level` INTEGER NOT NULL DEFAULT 1,
    `killed_by` TEXT COLLATE NOCASE NOT NULL,
    `is_player` INTEGER NOT NULL DEFAULT 1,
    `mostdamage_by` TEXT COLLATE NOCASE NOT NULL,
    `mostdamage_is_player` INTEGER NOT NULL DEFAULT 0,
    `unjustified` INTEGER NOT NULL DEFAULT 0,
    `mostdamage_unjustified` INTEGER NOT NULL DEFAULT 0,
    `participants` TEXT NOT NULL,
    CONSTRAINT `player_deaths_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `player_deaths_player_id_idx` ON `player_deaths` (`player_id`);
CREATE INDEX IF NOT EXISTS `player_deaths_killed_by_idx` ON `player_deaths` (`killed_by`);
CREATE INDEX IF NOT EXISTS `player_deaths_mostdamage_by_idx` ON `player_deaths` (`mostdamage_by`);

-- Table structure `player_depotitems`
CREATE TABLE IF NOT EXISTS `player_depotitems` (
    `player_id` INTEGER NOT NULL,
    `sid` INTEGER NOT NULL,
    `pid` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL DEFAULT 0,
    `count` INTEGER NOT NULL DEFAULT 0,
    `attributes` BLOB NOT NULL,
    CONSTRAINT `player_depotitems_unique` UNIQUE (`player_id`, `sid`),
    CONSTRAINT `player_depotitems_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_hirelings`
CREATE TABLE IF NOT EXISTS `player_hirelings` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `player_id` INTEGER NOT NULL,
    `name` TEXT,
    `active` INTEGER NOT NULL DEFAULT 0,
    `sex` INTEGER NOT NULL DEFAULT 0,
    `posx` INTEGER NOT NULL DEFAULT 0,
    `posy` INTEGER NOT NULL DEFAULT 0,
    `posz` INTEGER NOT NULL DEFAULT 0,
    `lookbody` INTEGER NOT NULL DEFAULT 0,
    `lookfeet` INTEGER NOT NULL DEFAULT 0,
    `lookhead` INTEGER NOT NULL DEFAULT 0,
    `looklegs` INTEGER NOT NULL DEFAULT 0,
    `looktype` INTEGER NOT NULL DEFAULT 136,
        FOREIGN KEY(`player_id`) REFERENCES `players`(`id`)
        ON DELETE CASCADE
);

-- Table structure `player_inboxitems`
CREATE TABLE IF NOT EXISTS `player_inboxitems` (
    `player_id` INTEGER NOT NULL,
    `sid` INTEGER NOT NULL,
    `pid` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL DEFAULT 0,
    `count` INTEGER NOT NULL DEFAULT 0,
    `attributes` BLOB NOT NULL,
    CONSTRAINT `player_inboxitems_unique` UNIQUE (`player_id`, `sid`),
    CONSTRAINT `player_inboxitems_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_items`
CREATE TABLE IF NOT EXISTS `player_items` (
    `player_id` INTEGER NOT NULL DEFAULT 0,
    `pid` INTEGER NOT NULL DEFAULT 0,
    `sid` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL DEFAULT 0,
    `count` INTEGER NOT NULL DEFAULT 0,
    `attributes` BLOB NOT NULL,
    CONSTRAINT `player_items_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `player_items_pk`
        PRIMARY KEY (`player_id`, `pid`, `sid`)
);
CREATE INDEX IF NOT EXISTS `player_items_player_id_idx` ON `player_items` (`player_id`);
CREATE INDEX IF NOT EXISTS `player_items_sid_idx` ON `player_items` (`sid`);

-- Table structure `player_wheeldata`
CREATE TABLE IF NOT EXISTS `player_wheeldata` (
	`player_id` INTEGER NOT NULL,
	`slot` BLOB NOT NULL,
	CONSTRAINT `player_wheeldata_players_fk`
		FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
		ON DELETE CASCADE,
    CONSTRAINT `player_wheeldata_pk`
      PRIMARY KEY (`player_id`)
);
CREATE INDEX IF NOT EXISTS `player_wheeldata_player_id_idx` ON `player_wheeldata` (`player_id`);

-- Table structure `player_kills`
CREATE TABLE IF NOT EXISTS `player_kills` (
    `player_id` INTEGER NOT NULL,
    `time` INTEGER NOT NULL DEFAULT 0,
    `target` INTEGER NOT NULL,
    `unavenged` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `player_kills_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_namelocks`
CREATE TABLE IF NOT EXISTS `player_namelocks` (
    `player_id` INTEGER NOT NULL,
    `reason` TEXT NOT NULL,
    `namelocked_at` INTEGER NOT NULL,
    `namelocked_by` INTEGER NOT NULL,
    CONSTRAINT `player_namelocks_unique` UNIQUE (`player_id`),
    CONSTRAINT `player_namelocks_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT `player_namelocks_players2_fk`
        FOREIGN KEY (`namelocked_by`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
CREATE INDEX IF NOT EXISTS `player_namelocks_namelocked_by_idx` ON `player_namelocks` (`namelocked_by`);

-- Table structure `player_prey`
CREATE TABLE IF NOT EXISTS `player_prey` (
    `player_id` INTEGER NOT NULL,
    `slot` INTEGER NOT NULL,
    `state` INTEGER NOT NULL,
    `raceid` TEXT NOT NULL,
    `option` INTEGER NOT NULL,
    `bonus_type` INTEGER NOT NULL,
    `bonus_rarity` INTEGER NOT NULL,
    `bonus_percentage` TEXT NOT NULL,
    `bonus_time` TEXT NOT NULL,
    `free_reroll` INTEGER NOT NULL,
    `monster_list` BLOB NULL,
    CONSTRAINT `player_prey_pk` PRIMARY KEY (`player_id`, `slot`),
    CONSTRAINT `player_prey_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_taskhunt`
CREATE TABLE IF NOT EXISTS `player_taskhunt` (
    `player_id` INTEGER NOT NULL,
    `slot` INTEGER NOT NULL,
    `state` INTEGER NOT NULL,
    `raceid` TEXT NOT NULL,
    `upgrade` INTEGER NOT NULL,
    `rarity` INTEGER NOT NULL,
    `kills` TEXT NOT NULL,
    `disabled_time` INTEGER NOT NULL,
    `free_reroll` INTEGER NOT NULL,
    `monster_list` BLOB NULL,
    CONSTRAINT `player_taskhunt_pk` PRIMARY KEY (`player_id`, `slot`),
    CONSTRAINT `player_taskhunt_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_bosstiary`
CREATE TABLE IF NOT EXISTS `player_bosstiary` (
    `player_id` INTEGER NOT NULL,
    `bossIdSlotOne` INTEGER NOT NULL DEFAULT 0,
    `bossIdSlotTwo` INTEGER NOT NULL DEFAULT 0,
    `removeTimes` INTEGER NOT NULL DEFAULT 1,
    `tracker` BLOB NOT NULL,
    CONSTRAINT `player_bosstiary_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_rewards`
CREATE TABLE IF NOT EXISTS `player_rewards` (
    `player_id` INTEGER NOT NULL,
    `sid` INTEGER NOT NULL,
    `pid` INTEGER NOT NULL DEFAULT 0,
    `itemtype` INTEGER NOT NULL DEFAULT 0,
    `count` INTEGER NOT NULL DEFAULT 0,
    `attributes` BLOB NOT NULL,
    CONSTRAINT `player_rewards_unique` UNIQUE (`player_id`, `sid`),
    CONSTRAINT `player_rewards_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_spells`
CREATE TABLE IF NOT EXISTS `player_spells` (
    `player_id` INTEGER NOT NULL,
    `name` TEXT NOT NULL,
    CONSTRAINT `player_spells_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE,
    CONSTRAINT `player_spells_pk` PRIMARY KEY (`player_id`, `name`)
);
CREATE INDEX IF NOT EXISTS `player_spells_player_id_idx` ON `player_spells` (`player_id`);

-- Table structure `player_stash`
CREATE TABLE IF NOT EXISTS `player_stash` (
    `player_id` INTEGER NOT NULL,
    `item_id` INTEGER NOT NULL,
    `item_count` INTEGER NOT NULL,
    CONSTRAINT `player_stash_pk` PRIMARY KEY (`player_id`, `item_id`),
    CONSTRAINT `player_stash_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `player_storage`
CREATE TABLE IF NOT EXISTS `player_storage` (
    `player_id` INTEGER NOT NULL DEFAULT 0,
    `key` INTEGER NOT NULL DEFAULT 0,
    `value` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `player_storage_pk` PRIMARY KEY (`player_id`, `key`),
    CONSTRAINT `player_storage_players_fk`
        FOREIGN KEY (`player_id`) REFERENCES `players` (`id`)
        ON DELETE CASCADE
);

-- Table structure `store_history`
CREATE TABLE IF NOT EXISTS `store_history` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `account_id` INTEGER NOT NULL,
    `mode` INTEGER NOT NULL DEFAULT 0,
    `description` TEXT NOT NULL,
    `coin_type` INTEGER NOT NULL DEFAULT 0,
    `coin_amount` INTEGER NOT NULL,
    `time` INTEGER NOT NULL,
    `timestamp` INTEGER NOT NULL DEFAULT 0,
    `coins` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `store_history_account_fk`
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
    ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `store_history_account_id_idx` ON `store_history` (`account_id`);

-- Table structure `tile_store`
CREATE TABLE IF NOT EXISTS `tile_store` (
    `house_id` INTEGER NOT NULL,
    `data` BLOB NOT NULL,
    CONSTRAINT `tile_store_account_fk`
        FOREIGN KEY (`house_id`) REFERENCES `houses` (`id`)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `tile_store_house_id_idx` ON `tile_store` (`house_id`);

-- Table structure `towns`
CREATE TABLE IF NOT EXISTS `towns` (
    `id` INTEGER PRIMARY KEY AUTOINCREMENT,
    `name` TEXT COLLATE NOCASE NOT NULL,
    `posx` INTEGER NOT NULL DEFAULT 0,
    `posy` INTEGER NOT NULL DEFAULT 0,
    `posz` INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT `name` UNIQUE (`name`)
);

-- Table structure `account_sessions`
CREATE TABLE IF NOT EXISTS `account_sessions` (
    `id` TEXT NOT NULL,
    `account_id` INTEGER NOT NULL,
    `expires` INTEGER NOT NULL,
    PRIMARY KEY (`id`),
    FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS `account_sessions_account_id_idx` ON `account_sessions` (`account_id`);

-- Table structure `kv_store`
CREATE TABLE IF NOT EXISTS `kv_store` (
    `key_name` TEXT NOT NULL,
    `timestamp` INTEGER NOT NULL,
    `value` BLOB NOT NULL,
    PRIMARY KEY (`key_name`)
);
