local commands = TalkAction("!commands")

function commands.onSay(player, words, param)
	local allTalkActions = Game.getTalkActions()
	local playerGroupId = player:getGroup():getId()

	-- pairs() walks the table in hash order, so sort the names to keep the
	-- list alphabetical.
	local names = {}
	for name in pairs(allTalkActions) do
		names[#names + 1] = name
	end
	table.sort(names)

	local text = "Available commands:\n\n"

	for _, name in ipairs(names) do
		local talkaction = allTalkActions[name]
		if talkaction:getGroupType() ~= 0 then
			if talkaction:getGroupType() <= playerGroupId then
				text = text .. talkaction:getName()

				local description = talkaction:getDescription()

				if description ~= "" then
					text = text .. " " .. description
				end

				text = text .. "\n\n"
			end
		end
	end

	player:showTextDialog(639, text)

	return true
end

commands:setDescription("[Usage]: !commands to see each command with its description")
commands:groupType("normal")
commands:register()
