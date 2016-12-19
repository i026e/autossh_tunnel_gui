export SHELL = sh

PACKAGE = autossh-gui

ifndef DESTDIR
	DESTDIR = "./debian/$(PACKAGE)/"
endif

all:

install: translations
	[ ! -d "$(DESTDIR)" ] || rm -r "$(DESTDIR)"

	mkdir -p "$(DESTDIR)usr/bin/"
	mkdir -p "$(DESTDIR)usr/share/$(PACKAGE)/"
	mkdir -p "$(DESTDIR)usr/share/applications/"

	install -D -m 0755 "./src/autossh-gui" "$(DESTDIR)usr/bin/$(PACKAGE)"

	cp "./src/autossh-gui.py" "$(DESTDIR)usr/share/$(PACKAGE)/"
	cp "./src/autossh-gui.glade" "$(DESTDIR)usr/share/$(PACKAGE)/"
	cp "./credits.txt" "$(DESTDIR)usr/share/$(PACKAGE)/"
	cp -r "./icons" "$(DESTDIR)usr/share/$(PACKAGE)/"


	cp "./src/autossh-gui.desktop" "$(DESTDIR)usr/share/applications/"

	cp -r locale "$(DESTDIR)usr/share"

debian:
	dh_make --createorig -y -s
	dpkg-source --commit
	debuild -us -uc

arch:
	cd ./arch
	makepkg

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
	rm -rf "$(DESTDIR)"
	rm -rf locale
	rm -rf .pc

