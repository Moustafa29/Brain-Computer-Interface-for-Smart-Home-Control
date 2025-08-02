import 'dart:math';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';

class SmartDeviceBox extends StatefulWidget {
  final String smartDeviceName;
  final String iconPath;
  final bool powerOn;
  final void Function(bool)? onChanged;
  final bool enabled;

  const SmartDeviceBox({
    super.key,
    required this.smartDeviceName,
    required this.iconPath,
    required this.powerOn,
    required this.onChanged,
    this.enabled = true,
  });

  @override
  State<SmartDeviceBox> createState() => _SmartDeviceBoxState();
}

class _SmartDeviceBoxState extends State<SmartDeviceBox> {
  bool _showStatus = false;

  void _toggleDevice() {
    if (!widget.enabled) return;

    final newState = !widget.powerOn;
    widget.onChanged?.call(newState);
    setState(() {
      _showStatus = true;
    });
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        setState(() {
          _showStatus = false;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _toggleDevice,
      child: Padding(
        padding: const EdgeInsets.all(15.0),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 200),
          child: _showStatus
              ? Container(
                  key: const ValueKey('status-view'),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(24),
                    color: widget.powerOn
                        ? Colors.grey[900]
                        : const Color.fromARGB(44, 164, 167, 189),
                  ),
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'STATUS',
                          style: TextStyle(
                            color: widget.powerOn
                                ? Colors.grey[400]
                                : Colors.grey[700],
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          widget.powerOn ? 'ON' : 'OFF',
                          style: TextStyle(
                            color: widget.powerOn ? Colors.white : Colors.black,
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
                    borderRadius: BorderRadius.circular(24),
                    color: widget.powerOn
                        ? Colors.grey[900]
                        : const Color.fromARGB(44, 164, 167, 189),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 25.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // icon
                        Image.asset(
                          widget.iconPath,
                          height: 65,
                          color: widget.powerOn
                              ? Colors.white
                              : Colors.grey.shade700,
                        ),

                        // smart device name + switch
                        Row(
                          children: [
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.only(left: 16.0),
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
                            ),
                            Transform.rotate(
                              angle: pi / 2,
                              child: Opacity(
                                opacity: widget.enabled ? 1.0 : 0.5,
                                child: CupertinoSwitch(
                                  value: widget.powerOn,
                                  onChanged: widget.enabled
                                      ? (value) {
                                          widget.onChanged?.call(value);
                                          setState(() {
                                            _showStatus = true;
                                          });
                                          Future.delayed(
                                              const Duration(seconds: 1), () {
                                            if (mounted) {
                                              setState(() {
                                                _showStatus = false;
                                              });
                                            }
                                          });
                                        }
                                      : null,
                                ),
                              ),
                            ),
                          ],
                        )
                      ],
                    ),
                  ),
                ),
        ),
      ),
    );
  }
}
