import processing.data.JSONObject;
import processing.data.JSONArray;

class ConfigManager {
  JSONObject config;

  ConfigManager(String filepath) {
    config = loadJSONObject(filepath);
  }

  boolean hasKey(String k) {
    return config.hasKey(k);
  }

  JSONObject getSonificationSetup() {
    if (config.hasKey("sonification_set_up"))
      return config.getJSONObject("sonification_set_up");
    return null;
  }

  String[] getDriverList() {
    JSONObject son = getSonificationSetup();
    if (son == null || !son.hasKey("drivers")) return new String[0];
    JSONArray arr = son.getJSONArray("drivers");
    String[] drivers = new String[arr.size()];
    for (int i = 0; i < arr.size(); i++) drivers[i] = arr.getString(i);
    return drivers;
  }

  String[] getListenerList() {
    JSONObject son = getSonificationSetup();
    if (son == null || !son.hasKey("listeners")) return new String[0];
    JSONArray arr = son.getJSONArray("listeners");
    String[] listeners = new String[arr.size()];
    for (int i = 0; i < arr.size(); i++) listeners[i] = arr.getString(i);
    return listeners;
  }

  JSONObject getConfig() {
    return config;
  }
}
