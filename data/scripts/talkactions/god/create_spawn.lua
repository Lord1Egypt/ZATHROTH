local createMonster = TalkAction("/spawn")

function createMonster.onSay(player, words, param)
	-- create log
	logCommand(player, words, param)

	if param == "" then
		player:sendCancelMessage("Command param required.")
		return true
	end

	-- ZATHROTH: "/spawn <number>" sets the server-wide spawn rate.
	if param:match("^%s*%d+%s*$") then
		return zathrothRateCommand(player, "spawn", param)
	end

	local spawn = Spawn()
	local parameter = param:split(",")
	local config = {
		{
			spawntime = tonumber(parameter[2]) or 60,
			monster = parameter[1],
			pos = player:getPosition(),
			status = true,
		},
	}
	spawn:setPositions(config)
	spawn:executeSpawn()
	player:getPosition():sendMagicEffect(CONST_ME_MAGIC_GREEN)
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "You have spawned " .. parameter[1] .. ".")
	return true
end

createMonster:separator(" ")
createMonster:setDescription("[Usage]: /spawn <multiplier> sets the monster spawn rate for the whole server; /spawn <monster>, [seconds] creates a spawn here")
createMonster:groupType("god")
createMonster:register()
