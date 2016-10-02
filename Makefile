export SHELL = sh

RSA_KEY = 425C42BE
PPA = i026e/udev-notify

INSTALL_DIR = ./debian/autossh-gui/

all:

install:
	[ ! -d "$(INSTALL_DIR)" ] || rm -r "$(INSTALL_DIR)"

	mkdir -p "$(INSTALL_DIR)usr/bin/"
	mkdir -p "$(INSTALL_DIR)usr/share/autossh-gui/"
	mkdir -p "$(INSTALL_DIR)usr/share/applications/"

	install -D -m 0755 "src/autossh-gui" "$(INSTALL_DIR)usr/bin/autossh-gui"

	cp "src/autossh-gui.py" "$(INSTALL_DIR)usr/share/autossh-gui/"
	cp "src/autossh-gui.glade" "$(INSTALL_DIR)usr/share/autossh-gui/"
	cp "credits.txt" "$(INSTALL_DIR)usr/share/autossh-gui/"
	cp -r "icons" "$(INSTALL_DIR)usr/share/autossh-gui/"


	cp "src/autossh-gui.desktop" "$(INSTALL_DIR)usr/share/applications/"



debian: install
	dh_make --createorig -y -s &
	dpkg-source --commit
	debuild -us -uc
#	debuild -S -k"$RSA_KEY"
#	dput -f ppa:$PPA ../*_source.changes


clean:
	rm -rf "$(INSTALL_DIR)"

