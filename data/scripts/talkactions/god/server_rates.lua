-- God commands for the server-wide rates in data/scripts/lib/zathroth_rates.lua.
-- "/spawn <number>" is handled by create_spawn.lua, which also creates spawns.
local commands = {
	{ words = "/setatkspeed", rate = "attackspeed", description = "[Usage]: /setatkspeed <multiplier>, player attack speed for the whole server (attacks cannot be faster than every 50 ms)" },
	{ words = "/lootrate", rate = "loot", description = "[Usage]: /lootrate <multiplier>, loot rate for the whole server" },
	{ words = "/exprate", rate = "exp", description = "[Usage]: /exprate <multiplier>, experience rate for the whole server" },
}

for _, command in ipairs(commands) do
	local talkAction = TalkAction(command.words)

	function talkAction.onSay(player, words, param)
		logCommand(player, words, param)
		return zathrothRateCommand(player, command.rate, param)
	end

	talkAction:separator(" ")
	talkAction:setDescription(command.description)
	talkAction:groupType("god")
	talkAction:register()
end
