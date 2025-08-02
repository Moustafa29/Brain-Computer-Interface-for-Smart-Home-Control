import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'dart:math';

class SmartFanBox extends StatefulWidget {
  final String smartDeviceName;
  final String iconPath;
  final bool powerOn;
  final Function(bool)? onChanged;
  final bool enabled;

  const SmartFanBox({
    super.key,
    required this.smartDeviceName,
    required this.iconPath,
    required this.powerOn,
    required this.onChanged,
    this.enabled = true,
  });

  @override
  State<SmartFanBox> createState() => _SmartFanBoxState();
}

class _SmartFanBoxState extends State<SmartFanBox> {
  int _fanSpeed = 0; // 0 = off, 1 = low, 2 = medium, 3 = high
  bool _showSpeedIndicator = false;

  void _cycleFanSpeed() {
    if (!widget.enabled) return;

    setState(() {
      _fanSpeed = (_fanSpeed + 1) % 4; // Cycles 0→1→2→3→0
      _showSpeedIndicator = true;
      if (_fanSpeed == 0) {
        widget.onChanged?.call(false);
      } else if (_fanSpeed == 1 && !widget.powerOn) {
        widget.onChanged?.call(true);
      }
    });

    // Hide speed indicator after 1 second
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        setState(() {
          _showSpeedIndicator = false;
        });
      }
    });
  }

  String _getSpeedLabel(int speed) {
    switch (speed) {
      case 1:
        return 'LOW';
      case 2:
        return 'MED';
      case 3:
        return 'HIGH';
      default:
        return 'OFF';
    }
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _cycleFanSpeed,
      child: Padding(
        padding: const EdgeInsets.all(15.0),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 300),
          child: _showSpeedIndicator
              ? Container(
                  key: const ValueKey('speed-view'),
                  decoration: BoxDecoration(
                    color: Colors.grey[900],
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'SPEED',
                          style: TextStyle(
                            color: Colors.grey[400],
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          _getSpeedLabel(_fanSpeed),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ),
                )
              : Container(
                  key: const ValueKey('normal-view'),
                  decoration: BoxDecoration(
                    color: widget.powerOn
                        ? Colors.grey[900]
                        : Color.fromARGB(44, 164, 167, 189),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // Icon - matches other device boxes
                        Image.asset(
                          widget.iconPath,
                          height: 65,
                          color:
                              widget.powerOn ? Colors.white : Colors.grey[800],
                        ),

                        // Device name and switch - EXACT match to other devices
                        Padding(
                          padding: const EdgeInsets.only(left: 18.0),
                          child: Row(
                            children: [
                              Expanded(
                                child: Text(
                                  widget.smartDeviceName,
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 16,
                                    color: widget.powerOn
                                        ? Colors.white
                                        : Colors.black,
                                  ),
                                ),
                              ),
                              Transform.rotate(
                                angle: pi / 2,
                                child: Opacity(
                                  opacity: widget.enabled ? 1.0 : 0.5,
                                  child: CupertinoSwitch(
                                    value: widget.powerOn,
                                    onChanged: widget.enabled
                                        ? widget.onChanged
                                        : null,
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
        ),
      ),
    );
  }
}
