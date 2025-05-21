find src -type f -name "*.py" -exec grep -lE '_\(|N\(_' {} \; >po/POTFILES
find data -type f \( -name "*.xml" -o -name "*.in" \) >>po/POTFILES
xgettext -o po/nyarchassistant.pot $(cat po/POTFILES)
cd po
for file in $(fd -e po); do
	msgmerge -U "$file" nyarchassistant.pot
done
rm -f *~
cd ..
