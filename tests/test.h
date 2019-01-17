namespace NameSpace {

class Base::ClassName : public Base::BaseClass {
public:
	ClassName();
	ClassName(const ARG &);
	ClassName(
		const ARG &,
		const std::string &ARG2,
		const std::string &ARG3,
		const std::string &ARG3 = std::string()
	);
	virtual bool isValid() const = 0;
	virtual ~ClassName();
	virtual NameSpace2::ClassC process(const NameSpace2::ClassC &) = 0;

	bool init();
	bool setting(const ARG &);
	virtual NameSpace2::ClassC process(const NameSpace2::ClassC &);
	virtual bool isValid() const { return isCredValid() && _conn.isValid(); }
	const ARG &getSet() const { return _conn; }
protected:
	SYNO_CRED *_pCred;
	SYNO_CRED_SESS *_pSess;
	ARG _conn;
};

}//NameSpace

class Base: public Base::BaseClass {
public:
	Base();
}