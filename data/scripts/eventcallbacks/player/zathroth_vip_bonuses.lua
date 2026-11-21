-- Fires after an item with an equip event is put on or taken off, and for
-- every worn item at login; data/scripts/lib/zathroth_vip.lua rebuilds the
-- VIP bonuses from the current equipment.
local callback = EventCallback("ZathrothVipBonuses")

function callback.playerOnInventoryUpdate(player, item, slot, equip)
	zathrothVipRefresh(player)
end

callback:register()

local logout = CreatureEvent("ZathrothVipLogout")

function logout.onLogout(player)
	zathrothVipRememberVitals(player)
	return true
end

logout:register()

local login = CreatureEvent("ZathrothVipLogin")

function login.onLogin(player)
	zathrothVipRestoreVitals(player)
	return true
end

login:register()
