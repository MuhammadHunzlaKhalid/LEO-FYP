import 'package:flutter/material.dart';
import 'api_service.dart';
import 'session.dart';

class MyRegister extends StatefulWidget {
  const MyRegister({super.key});
  @override
  State<MyRegister> createState() => _MyRegisterState();
}

class _MyRegisterState extends State<MyRegister> {
  final _nameCtrl  = TextEditingController();
  final _userCtrl  = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _passCtrl  = TextEditingController();
  bool _loading = false;
  bool _obscure = true;
  String? _error;
  String? _success;

  Future<void> _register() async {
    final name = _nameCtrl.text.trim();
    final user = _userCtrl.text.trim();
    final phone = _phoneCtrl.text.trim();
    if (name.isEmpty || user.isEmpty) {
      setState(() => _error = 'Name and username are required.'); return;
    }
    if (user.contains(' ')) {
      setState(() => _error = 'Username cannot contain spaces.'); return;
    }
    setState(() { _loading = true; _error = null; _success = null; });
    final ok = await ApiService.register(username: user, name: name, phone: phone);
    setState(() => _loading = false);
    if (ok) {
      Session.set(user, name: name);
      setState(() => _success = 'Account created! Redirecting...');
      await Future.delayed(const Duration(milliseconds: 800));
      if (mounted) Navigator.pushReplacementNamed(context, 'home');
    } else {
      setState(() => _error = 'Could not reach server. Is the backend running?');
    }
  }

  @override
  void dispose() {
    _nameCtrl.dispose(); _userCtrl.dispose();
    _phoneCtrl.dispose(); _passCtrl.dispose(); super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        image: DecorationImage(
            image: AssetImage('assets/regbackground.jpg'), fit: BoxFit.cover)),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0),
        body: Stack(children: [
          Container(
            padding: const EdgeInsets.only(left: 35, top: 20),
            child: const Text('Create Account',
                style: TextStyle(color: Colors.white, fontSize: 33,
                    fontWeight: FontWeight.w700)),
          ),

          SingleChildScrollView(
            child: Container(
              padding: EdgeInsets.only(
                top: MediaQuery.of(context).size.height * 0.22,
                left: 35, right: 35,
              ),
              child: Column(children: [
                _field(_nameCtrl,  'Full Name',      Icons.person_outline),
                const SizedBox(height: 20),
                _field(_userCtrl,  'Username (no spaces)', Icons.badge_outlined),
                const SizedBox(height: 20),
                _field(_phoneCtrl, 'Phone Number',   Icons.phone_outlined,
                    type: TextInputType.phone),
                const SizedBox(height: 20),
                TextField(
                  controller: _passCtrl,
                  obscureText: _obscure,
                  decoration: InputDecoration(
                    fillColor: Colors.grey.shade100, filled: true,
                    hintText: 'Password',
                    prefixIcon: const Icon(Icons.lock_outline),
                    suffixIcon: IconButton(
                      icon: Icon(_obscure
                          ? Icons.visibility_off : Icons.visibility,
                          color: Colors.grey),
                      onPressed: () => setState(() => _obscure = !_obscure),
                    ),
                    border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10)),
                  ),
                ),

                if (_error != null) ...[
                  const SizedBox(height: 10),
                  _msgBox(_error!, Colors.red, Icons.error_outline),
                ],
                if (_success != null) ...[
                  const SizedBox(height: 10),
                  _msgBox(_success!, Colors.green, Icons.check_circle_outline),
                ],

                const SizedBox(height: 40),

                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                  GestureDetector(
                    onTap: _loading ? null : _register,
                    child: const Text('Sign Up', style: TextStyle(
                        color: Colors.white, fontSize: 27,
                        fontWeight: FontWeight.w700)),
                  ),
                  CircleAvatar(
                    radius: 30,
                    backgroundColor: const Color(0xff4c505b),
                    child: _loading
                        ? const CircularProgressIndicator(
                            color: Colors.white, strokeWidth: 2)
                        : IconButton(
                            color: Colors.white,
                            onPressed: _register,
                            icon: const Icon(Icons.arrow_forward)),
                  ),
                ]),

                const SizedBox(height: 30),
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                  TextButton(
                    onPressed: () =>
                        Navigator.pushReplacementNamed(context, 'login'),
                    child: const Text('Sign In', style: TextStyle(
                        decoration: TextDecoration.underline,
                        fontSize: 18, color: Colors.white)),
                  ),
                  TextButton(
                    onPressed: () {},
                    child: const Text('Forget Password', style: TextStyle(
                        decoration: TextDecoration.underline,
                        fontSize: 18, color: Colors.white)),
                  ),
                ]),
                const SizedBox(height: 30),
              ]),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _field(TextEditingController c, String hint, IconData icon,
      {TextInputType type = TextInputType.text}) =>
      TextField(
        controller: c,
        keyboardType: type,
        decoration: InputDecoration(
          fillColor: Colors.grey.shade100, filled: true,
          hintText: hint,
          prefixIcon: Icon(icon),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );

  Widget _msgBox(String msg, Color color, IconData icon) =>
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
            color: color.withOpacity(0.15),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color)),
        child: Row(children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(width: 8),
          Expanded(child: Text(msg,
              style: TextStyle(color: color, fontSize: 13))),
        ]),
      );
}
