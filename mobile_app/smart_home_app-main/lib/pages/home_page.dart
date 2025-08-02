import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:simple_ui/util/smart_fan_box.dart';
import 'package:simple_ui/util/smart_device_box.dart';
import 'package:simple_ui/util/smart_light_box.dart';
import 'package:simple_ui/util/environment_components.dart';
import 'package:simple_ui/components/app_drawer.dart';
import 'package:simple_ui/pages/login_page.dart';

// Add this enum at the top of the file
enum ControlMode {
  bciOnly,
  mobileOnly,
  both,
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final double horizontalPadding = 30;
  final double verticalPadding = 25;
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  // Control mode state
  ControlMode controlMode = ControlMode.mobileOnly;

  List<String> rooms = ["Living Room", "Bedroom", "Kitchen", "Garage"];
  int selectedRoomIndex = 0;

  List mySmartDevices = [
    ["Smart Light", "lib/icons/light-bulb.png", true],
    ["Smart Window", "lib/icons/windows.png", false],
    ["Smart Door", "lib/icons/house-door.png", false],
    ["Smart Fan", "lib/icons/fan.png", false],
  ];

  void powerSwitchChanged(bool value, int index) {
    // Check control mode before allowing changes
    if (controlMode == ControlMode.bciOnly) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Device control currently set to BCI only'),
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    setState(() {
      mySmartDevices[index][2] = value;
    });
  }

  void toggleAllDevices(bool value) {
    // Check control mode before allowing changes
    if (controlMode == ControlMode.bciOnly) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Device control currently set to BCI only'),
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    setState(() {
      for (var device in mySmartDevices) {
        device[2] = value;
      }
    });
  }

  // Method to update control mode and handle enabling/disabling controls
  void _updateControlMode(ControlMode newMode) {
    setState(() {
      controlMode = newMode;
    });

    // Here you would integrate with your actual BCI system
    // For now, we'll just print and show snackbars
    switch (newMode) {
      case ControlMode.bciOnly:
        // Disable mobile controls, enable BCI
        print('BCI control enabled, mobile controls disabled');
        break;
      case ControlMode.mobileOnly:
        // Disable BCI, enable mobile controls
        print('Mobile controls enabled, BCI control disabled');
        break;
      case ControlMode.both:
        // Enable both
        print('Both BCI and mobile controls enabled');
        break;
    }
  }

  // Method to cycle through control modes
  void _cycleControlMode() {
    ControlMode newMode;
    String message;
    Color? snackbarColor;

    switch (controlMode) {
      case ControlMode.mobileOnly:
        newMode = ControlMode.bciOnly;
        message = 'Control mode changed to BCI only (mobile controls disabled)';
        break;
      case ControlMode.bciOnly:
        newMode = ControlMode.both;
        message = 'Control mode changed to BOTH (may cause interference)';
        snackbarColor = Colors.orange;
        break;
      case ControlMode.both:
        newMode = ControlMode.mobileOnly;
        message = 'Control mode changed to Mobile only (BCI controls disabled)';
        break;
    }

    _updateControlMode(newMode);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        duration: Duration(seconds: 3),
        behavior: SnackBarBehavior.floating,
        backgroundColor: snackbarColor,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      backgroundColor: Colors.grey[300],
      drawer: AppDrawer(
        onLogout: () {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (context) => const LoginPage()),
          );
        },
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Top bar
            Padding(
              padding: EdgeInsets.symmetric(
                horizontal: horizontalPadding,
                vertical: verticalPadding,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  IconButton(
                    icon: Image.asset(
                      'lib/icons/menu.png',
                      height: 30,
                      color: Colors.grey[800],
                    ),
                    onPressed: () => _scaffoldKey.currentState?.openDrawer(),
                  ),
                  PopupMenuButton<String>(
                    icon: Icon(Icons.person, size: 35, color: Colors.grey[800]),
                    onSelected: (value) {
                      if (value == 'logout') {
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                              builder: (context) => const LoginPage()),
                        );
                      }
                    },
                    itemBuilder: (context) => [
                      const PopupMenuItem(
                          value: 'profile', child: Text('Edit Profile')),
                      const PopupMenuItem(
                          value: 'settings', child: Text('Settings')),
                      const PopupMenuDivider(),
                      const PopupMenuItem(
                          value: 'logout', child: Text('Log Out')),
                    ],
                  ),
                ],
              ),
            ),

            const SizedBox(height: 0),

            // Welcome section
            Padding(
              padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text("Welcome Home,",
                      style:
                          TextStyle(fontSize: 20, color: Colors.grey.shade800)),
                  Text('Mohamed Ragb',
                      style: GoogleFonts.bebasNeue(fontSize: 62)),
                ],
              ),
            ),

            const SizedBox(height: 20),

            // Hazard alert or environment display
            StreamBuilder<EnvironmentData>(
              stream: EnvironmentService().stream,
              builder: (context, snapshot) {
                final data = snapshot.data ?? EnvironmentData.empty();

                // Display alert banner if either hazard occurs
                if (data.gasLeak || data.flameDetected) {
                  return HazardAlertBanner(
                    alertType: data.gasLeak && data.flameDetected
                        ? 'both'
                        : data.gasLeak
                            ? 'gas'
                            : 'flame',
                  );
                }

                return SensorStatusBar(
                  temperature: data.temperature,
                  humidity: data.humidity,
                  gasLeak: data.gasLeak,
                  flameDetected: data.flameDetected,
                );
              },
            ),

            const SizedBox(height: 10),

            const SizedBox(height: 15),

            // Quick actions
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  ElevatedButton.icon(
                    icon: const Icon(Icons.power_settings_new, size: 18),
                    label: const Text('All On'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => toggleAllDevices(true),
                  ),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.power_off, size: 18),
                    label: const Text('All Off'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => toggleAllDevices(false),
                  ),
                ],
              ),
            ),

            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 40.0),
              child: Divider(
                  thickness: 1, color: Color.fromARGB(255, 204, 204, 204)),
            ),

            const SizedBox(height: 10),

            // Smart devices header
            Padding(
              padding: EdgeInsets.symmetric(horizontal: horizontalPadding),
              child: Row(
                children: [
                  Text(
                    "Smart Devices",
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 24,
                      color: Colors.grey.shade800,
                    ),
                  ),
                  const Spacer(),
                  // Control mode toggle button
                  IconButton(
                    icon: Image.asset(
                      'lib/icons/change.png',
                      height: 18,
                    ),
                    onPressed: _cycleControlMode,
                    tooltip:
                        'Change control mode (Current: ${controlMode.toString().split('.').last})',
                  ),
                  IconButton(
                    icon: const Icon(Icons.add),
                    onPressed: () {
                      showModalBottomSheet(
                        context: context,
                        builder: (context) => Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            ListTile(
                              leading: const Icon(Icons.add),
                              title: const Text('Add New Device'),
                              onTap: () => Navigator.pop(context),
                            ),
                            ListTile(
                              leading: const Icon(Icons.settings),
                              title: const Text('Quick Settings'),
                              onTap: () => Navigator.pop(context),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ],
              ),
            ),

            const SizedBox(height: 10),

            // Horizontal room selection bar
            Container(
              height: 40,
              margin: const EdgeInsets.symmetric(horizontal: 25),
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: rooms.length,
                itemBuilder: (context, index) {
                  final isSelected = selectedRoomIndex == index;
                  return GestureDetector(
                    onTap: () {
                      if (controlMode == ControlMode.bciOnly) {
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(
                            content: Text(
                                'Room selection currently set to BCI only'),
                            duration: Duration(seconds: 2),
                          ),
                        );
                        return;
                      }
                      setState(() => selectedRoomIndex = index);
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 16, vertical: 8),
                      margin: const EdgeInsets.only(right: 10),
                      decoration: isSelected
                          ? BoxDecoration(
                              color: Colors.blueGrey.shade700,
                              borderRadius: BorderRadius.circular(20),
                              boxShadow: [
                                BoxShadow(
                                  color: Colors.black.withOpacity(0.1),
                                  blurRadius: 4,
                                  offset: const Offset(0, 2),
                                ),
                              ],
                            )
                          : null,
                      child: Text(
                        rooms[index],
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight:
                              isSelected ? FontWeight.w600 : FontWeight.w500,
                          letterSpacing: 0.3,
                          color: isSelected ? Colors.white : Colors.grey[700],
                          fontFamily: 'Roboto',
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),

            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 40.0),
              child: Divider(
                  thickness: 1, color: Color.fromARGB(255, 204, 204, 204)),
            ),

            // Smart devices grid
            Expanded(
              child: GridView.builder(
                itemCount: mySmartDevices.length,
                padding: const EdgeInsets.symmetric(horizontal: 25),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  childAspectRatio: 1 / 1.25,
                ),
                itemBuilder: (context, index) {
                  if (mySmartDevices[index][0] == "Smart Light") {
                    return SmartLightBox(
                      smartDeviceName: mySmartDevices[index][0],
                      iconPath: mySmartDevices[index][1],
                      powerOn: mySmartDevices[index][2],
                      onChanged: (value) => powerSwitchChanged(value, index),
                      // Disable interaction in BCI-only mode
                      enabled: controlMode != ControlMode.bciOnly,
                    );
                  } else if (mySmartDevices[index][0] == "Smart Fan") {
                    return SmartFanBox(
                      smartDeviceName: mySmartDevices[index][0],
                      iconPath: mySmartDevices[index][1],
                      powerOn: mySmartDevices[index][2],
                      onChanged: (value) => powerSwitchChanged(value, index),
                      // Disable interaction in BCI-only mode
                      enabled: controlMode != ControlMode.bciOnly,
                    );
                  }
                  return SmartDeviceBox(
                    smartDeviceName: mySmartDevices[index][0],
                    iconPath: mySmartDevices[index][1],
                    powerOn: mySmartDevices[index][2],
                    onChanged: (value) => powerSwitchChanged(value, index),
                    // Disable interaction in BCI-only mode
                    enabled: controlMode != ControlMode.bciOnly,
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
