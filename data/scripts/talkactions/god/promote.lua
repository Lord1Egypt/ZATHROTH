-- Promotes a character. data/scripts/creaturescripts/player/login.lua keeps
-- the promotion (KV "promoted") only while the account is premium.
local promote = TalkAction("/promote")

function promote.onSay(player, words, param)
	logCommand(player, words, param)

	local target = param ~= "" and Player(param:trim())
	if not target then
		player:sendCancelMessage("Usage: /promote <online player name>")
		return true
	end

	local promotion = target:getVocation():getPromotion()
	if target:isPromoted() or not promotion then
		player:sendCancelMessage(target:getName() .. " is already promoted or has no promotion.")
		return true
	end

	target:setVocation(promotion)
	target:kv():set("promoted", true)
	target:getPosition():sendMagicEffect(CONST_ME_HOLYDAMAGE)
	target:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("You have been promoted to %s.", promotion:getName()))
	local note = target:isPremium() and "" or " It lasts only while the account is premium; use /addpremium."
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format("%s is now %s.%s", target:getName(), promotion:getName(), note))
	return true
end

promote:separator(" ")
promote:setDescription("[Usage]: /promote <player name>, promotes the character (needs premium to keep it)")
promote:groupType("god")
promote:register()
