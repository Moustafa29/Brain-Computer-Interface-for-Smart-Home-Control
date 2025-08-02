import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'dart:math';

class SmartLightBox extends StatefulWidget {
  final String smartDeviceName;
  final String iconPath;
  final bool powerOn;
  final Function(bool)? onChanged;
  final bool enabled;

  const SmartLightBox({
    super.key,
    required this.smartDeviceName,
    required this.iconPath,
    required this.powerOn,
    required this.onChanged,
    this.enabled = true,
  });

  @override
  State<SmartLightBox> createState() => _SmartLightBoxState();
}

class _SmartLightBoxState extends State<SmartLightBox> {
  double _lightIntensity = 0.7; // Default intensity (70%)
  bool _showIntensity = false;
  bool _showSlider = false;

  void _onTap() {
    if (!widget.enabled) return;

    // Simple tap - toggle on/off and show intensity briefly
    final newState = !widget.powerOn;
    widget.onChanged?.call(newState);

    setState(() {
      _showIntensity = true;
      _showSlider = false;

      if (newState) {
        // Turning on - set to default 70% if it was 0
        if (_lightIntensity == 0) {
          _lightIntensity = 0.7;
        }
      } else {
        // Turning off - set intensity to 0
        _lightIntensity = 0;
      }
    });

    // Hide intensity display after 1.5 seconds
    Future.delayed(const Duration(milliseconds: 1700), () {
      if (mounted) {
        setState(() {
          _showIntensity = false;
        });
      }
    });
  }

  void _onLongPress() {
    if (!widget.enabled) return;

    // Long press - show slider for intensity control (only if light is on)
    if (widget.powerOn) {
      setState(() {
        _showIntensity = true;
        _showSlider = true;

        // Start with minimum 10% when opening slider
        if (_lightIntensity == 0) {
          _lightIntensity = 0.1;
        }
      });
    }
  }

  void _hideSlider() {
    // Hide slider when tapping outside or after interaction
    setState(() {
      _showSlider = false;
    });

    Future.delayed(const Duration(milliseconds: 600), () {
      if (mounted) {
        setState(() {
          _showIntensity = false;
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _showSlider ? _hideSlider : _onTap,
      onLongPress: _onLongPress,
      child: Padding(
        padding: const EdgeInsets.all(15.0),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 700),
          child: _showIntensity && widget.powerOn
              ? Container(
                  key: const ValueKey('intensity-view'),
                  decoration: BoxDecoration(
                    color: Colors.grey[900],
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 20),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        Text(
                          'INTENSITY',
                          style: TextStyle(
                            color: Colors.grey[400],
                            fontSize: 14,
                          ),
                        ),
                        const SizedBox(height: 0),
                        Text(
                          '${(_lightIntensity * 100).toInt()}%',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                          ),
                        ),

                        // Show slider only on long press
                        if (_showSlider) ...[
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 14, vertical: 0),
                            child: Slider(
                              value: _lightIntensity,
                              min: 0.1, // Minimum 10%
                              max: 1.0,
                              onChanged: widget.enabled
                                  ? (value) {
                                      setState(() {
                                        _lightIntensity = value;
                                      });
                                    }
                                  : null,
                              activeColor: Colors.amber,
                              inactiveColor: Colors.grey[600],
                            ),
                          ),
                          const SizedBox(height: 0),
                          Center(
                            child: Text(
                              'Tap to close',
                              style: TextStyle(
                                color: Colors.grey[500],
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ] else ...[
                          const SizedBox(height: 0),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 4, vertical: 0),
                            child: Text(
                              'Hold to adjust intensity',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: Colors.grey[500],
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],

                        const SizedBox(height: 10),
                      ],
                    ),
                  ),
                )
              : Container(
                  key: const ValueKey('normal-view'),
                  decoration: BoxDecoration(
                    color: widget.powerOn
                        ? Colors.grey[900]
                        : const Color.fromARGB(44, 164, 167, 189),
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 25.0),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        // Icon with intensity-based brightness
                        Image.asset(
                          widget.iconPath,
                          height: 65,
                          color: widget.powerOn
                              ? Colors.amber
                                  .withOpacity(0.3 + (_lightIntensity * 0.7))
                              : Colors.grey[800],
                        ),

                        // Device name and switch
                        Padding(
                          padding: const EdgeInsets.only(left: 16.0, right: 10),
                          child: Row(
                            children: [
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      widget.smartDeviceName,
                                      style: TextStyle(
                                        fontWeight: FontWeight.bold,
                                        fontSize: 16,
                                        color: widget.powerOn
                                            ? Colors.white
                                            : Colors.black,
                                      ),
                                    ),
                                    if (widget.powerOn)
                                      Text(
                                        '${(_lightIntensity * 100).toInt()}%',
                                        style: TextStyle(
                                          color: Colors.grey[400],
                                          fontSize: 12,
                                        ),
                                      ),
                                  ],
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
                                              if (!value) {
                                                _lightIntensity = 0;
                                              } else if (_lightIntensity == 0) {
                                                _lightIntensity =
                                                    0.7; // Default to 70%
                                              }
                                            });
                                          }
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
