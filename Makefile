export SHELL = sh

RSA_KEY = 425C42BE
PPA = i026e/udev-notify

PACKAGE = autossh-gui
INSTALL_DIR = "./debian/$(PACKAGE)/"

all:

install: translations
	[ ! -d "$(INSTALL_DIR)" ] || rm -r "$(INSTALL_DIR)"

	mkdir -p "$(INSTALL_DIR)usr/bin/"
	mkdir -p "$(INSTALL_DIR)usr/share/$(PACKAGE)/"
	mkdir -p "$(INSTALL_DIR)usr/share/applications/"

	install -D -m 0755 "./src/autossh-gui" "$(INSTALL_DIR)usr/bin/$(PACKAGE)"

	cp "./src/autossh-gui.py" "$(INSTALL_DIR)usr/share/$(PACKAGE)/"
	cp "./src/autossh-gui.glade" "$(INSTALL_DIR)usr/share/$(PACKAGE)/"
	cp "./credits.txt" "$(INSTALL_DIR)usr/share/$(PACKAGE)/"
	cp -r "./icons" "$(INSTALL_DIR)usr/share/$(PACKAGE)/"


	cp "./src/autossh-gui.desktop" "$(INSTALL_DIR)usr/share/applications/"

	cp -r locale "$(INSTALL_DIR)usr/share"



debian:
	dh_make --createorig -y -s
	dpkg-source --commit
	debuild -us -uc
#	debuild -S -k"$RSA_KEY"
#	dput -f ppa:$PPA ../*_source.changes

pot:
	mkdir -p ./po
	xgettext --default-domain="$(PACKAGE)" --sort-output --output="./po/$(PACKAGE).pot" ./src/*.py
	xgettext --join-existing --sort-output -L Glade -k_ -kN_ --keyword=translatable --output="./po/$(PACKAGE).pot" ./src/*.glade

	sed -i 's/CHARSET/UTF-8/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE VERSION/$(PACKAGE) $(VERSION)/' po/$(PACKAGE).pot
	sed -i 's/PACKAGE/$(PACKAGE)/' po/$(PACKAGE).pot

update-po: pot
	for i in po/*.po ;\
	do \
	mv $$i $${i}.old ; \
	(msgmerge $${i}.old po/$(PACKAGE).pot | msgattrib --no-obsolete > $$i) ; \
	rm $${i}.old ; \
	done

translations: ./po/*.po
	mkdir -p locale
	@for po in $^; do \
		language=`basename $$po`; \
		language=$${language%%.po}; \
		target="locale/$$language/LC_MESSAGES"; \
		mkdir -p $$target; \
		msgfmt --output=$$target/$(PACKAGE).mo $$po; \
	done

clean:
	rm -rf "$(INSTALL_DIR)"
	rm -rf locale

