import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppDrawer extends StatelessWidget {
  final VoidCallback onLogout;

  const AppDrawer({super.key, required this.onLogout});

  @override
  Widget build(BuildContext context) {
    return Drawer(
      width: MediaQuery.of(context).size.width * 0.7,
      backgroundColor: Colors.grey[900],
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          _buildHeader(context),
          _buildDrawerItem(
            context,
            icon: Icons.home,
            title: 'Dashboard',
            onTap: () => Navigator.pop(context),
          ),
          _buildDrawerItem(
            context,
            icon: Icons.settings,
            title: 'Settings',
            onTap: () => _navigateTo(context, '/settings'),
          ),
          _buildDrawerItem(
            context,
            icon: Icons.devices,
            title: 'All Devices',
            onTap: () => _navigateTo(context, '/devices'),
          ),
          _buildDrawerItem(
            context,
            icon: Icons.history,
            title: 'Usage History',
            onTap: () => _navigateTo(context, '/history'),
          ),
          SizedBox(
            height: 280,
          ),
          const Divider(color: Colors.grey),
          _buildDrawerItem(
            context,
            icon: Icons.logout,
            title: 'Log Out',
            onTap: onLogout,
          ),
        ],
      ),
    );
  }

  Widget _buildHeader(BuildContext context) {
    return DrawerHeader(
      decoration: BoxDecoration(
        color: Colors.blue[800],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const CircleAvatar(
            radius: 30,
            backgroundImage: AssetImage('lib/icons/user_profile.png'),
          ),
          const SizedBox(height: 10),
          Text(
            'Mohamed Ragb',
            style: GoogleFonts.bebasNeue(
              fontSize: 24,
              color: Colors.white,
            ),
          ),
          Text(
            'Admin',
            style: TextStyle(color: Colors.grey[300]),
          ),
        ],
      ),
    );
  }

  Widget _buildDrawerItem(
    BuildContext context, {
    required IconData icon,
    required String title,
    required VoidCallback onTap,
  }) {
    return ListTile(
      leading: Icon(icon, color: Colors.white),
      title: Text(
        title,
        style: TextStyle(color: Colors.white),
      ),
      onTap: onTap,
    );
  }

  void _navigateTo(BuildContext context, String route) {
    Navigator.pop(context);
    Navigator.pushNamed(context, route);
  }
}
