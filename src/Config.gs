/**
 * Чтение конфигурации из листа Config и PropertiesService.
 * Кэширование через CacheService (TTL 5–10 мин).
 */
var CONFIG_SHEET = 'Config';
var CACHE_TTL = 300; // 5 минут
var PROP_BOT_TOKEN = 'BOT_TOKEN';
var PROP_CHAT_ID = 'CHAT_ID';

function getConfigSheet() {
  return getSheet(CONFIG_SHEET);
}

function _getConfigMap() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('config_map');
  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) {}
  }
  var sheet = getConfigSheet();
  if (!sheet) return {};
  var data = sheet.getDataRange().getValues();
  var map = {};
  for (var i = 1; i < data.length; i++) {
    var key = data[i][0];
    var val = data[i][1];
    if (key != null && key !== '') map[String(key)] = val;
  }
  cache.put('config_map', JSON.stringify(map), CACHE_TTL);
  return map;
}

function _getConfigParam(name) {
  var map = _getConfigMap();
  return map[name];
}

function getFixedSalary() {
  var v = _getConfigParam('FixedSalary');
  return v != null && v !== '' ? Number(v) : 0;
}

function getSecondJobPercent() {
  var v = _getConfigParam('SecondJobPercent');
  return v != null && v !== '' ? Number(v) : 0;
}

function getPayDay1() {
  var v = _getConfigParam('PayDay1');
  return v != null && v !== '' ? Number(v) : 10;
}

function getPayDay2() {
  var v = _getConfigParam('PayDay2');
  return v != null && v !== '' ? Number(v) : 25;
}

function getWorkHoursNorm() {
  var v = _getConfigParam('WorkHoursNorm');
  return v != null && v !== '' ? Number(v) : 8;
}

function getBotToken() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('bot_token');
  if (cached) return cached;
  var token = PropertiesService.getScriptProperties().getProperty(PROP_BOT_TOKEN);
  if (token) {
    cache.put('bot_token', token, CACHE_TTL);
    return token;
  }
  token = _getConfigParam('BotToken');
  if (token) {
    cache.put('bot_token', token, CACHE_TTL);
    return token;
  }
  return null;
}

function getChatId() {
  var cache = CacheService.getScriptCache();
  var cached = cache.get('chat_id');
  if (cached) return String(cached).trim();
  var id = PropertiesService.getScriptProperties().getProperty(PROP_CHAT_ID);
  if (id) {
    id = String(id).trim();
    cache.put('chat_id', id, CACHE_TTL);
    return id;
  }
  var fromSheet = _getConfigParam('ChatID');
  if (fromSheet != null && fromSheet !== '') {
    var sid = String(fromSheet).trim();
    cache.put('chat_id', sid, CACHE_TTL);
    return sid;
  }
  return null;
}

function invalidateConfigCache() {
  var cache = CacheService.getScriptCache();
  cache.remove('config_map');
  cache.remove('bot_token');
  cache.remove('chat_id');
}
