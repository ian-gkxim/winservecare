import { ExpoConfig, ConfigContext } from "expo/config";

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: "WinServeCare",
  slug: "winservecare-mobile",
  version: "1.0.0",
  orientation: "portrait",
  userInterfaceStyle: "light",
  ios: {
    supportsTablet: false,
    bundleIdentifier: "com.winservecare.mobile",
    infoPlist: {
      NSLocationAlwaysAndWhenInUseUsageDescription:
        "WinServeCare needs your location to track visit progress and provide accurate arrival/departure times.",
      NSLocationWhenInUseUsageDescription:
        "WinServeCare needs your location to track visit progress.",
      NSLocationAlwaysUsageDescription:
        "WinServeCare needs background location access to track visit progress even when the app is not in the foreground.",
      UIBackgroundModes: ["location", "fetch", "remote-notification"],
    },
  },
  android: {
    adaptiveIcon: {
      backgroundColor: "#ffffff",
    },
    package: "com.winservecare.mobile",
    permissions: [
      "ACCESS_FINE_LOCATION",
      "ACCESS_COARSE_LOCATION",
      "ACCESS_BACKGROUND_LOCATION",
      "FOREGROUND_SERVICE",
      "FOREGROUND_SERVICE_LOCATION",
      "RECEIVE_BOOT_COMPLETED",
    ],
  },
  plugins: [
    [
      "expo-location",
      {
        locationAlwaysAndWhenInUsePermission:
          "WinServeCare needs your location to track visit progress and provide accurate arrival/departure times.",
        locationAlwaysPermission:
          "WinServeCare needs background location access to track visit progress even when the app is not in the foreground.",
        locationWhenInUsePermission:
          "WinServeCare needs your location to track visit progress.",
        isAndroidBackgroundLocationEnabled: true,
        isAndroidForegroundServiceEnabled: true,
      },
    ],
  ],
  extra: {
    eas: {
      projectId: "your-project-id",
    },
  },
});
