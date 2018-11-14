namespace NameSpace {

ClassName::ClassName() {

}
ClassName::ClassName(const ARG &) {

}
ClassName::ClassName(
	const ARG &,
	const std::string &ARG2,
	const std::string &ARG3,
	const std::string &ARG3 = std::string()) {

}
bool ClassName::isValid() {

}
ClassName::~ClassName() {

}
NameSpace2::ClassC ClassName::process(const NameSpace2::ClassC &) {

}
bool ClassName::init() {

}
bool ClassName::setting(const ARG &) {

}
NameSpace2::ClassC ClassName::process(const NameSpace2::ClassC &) {

}
bool ClassName::isValid() const {
	return isCredValid() && _conn.isValid();
}
const ARG &ClassName::getSet() const {
	return _conn;
}

class ClassNameB : public Base::BaseClass {
}

const ARG &ClassNameB::ClassNameB() {

}

class ClassNameC;

const ARG &FuncA() {
}

static AAA::BBB
CCC(const std::string &DDD)	// function name parsing error by C++.sublime-syntax
{
}

}//NameSpace