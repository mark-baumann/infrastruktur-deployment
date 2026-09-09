#!/bin/sh
# Temporary fix for AUG-370: WordPress asks for FTP credentials on theme install
# because the web process cannot write to wp-content directly.
#  1. Enable FS_METHOD=direct in wp-config.php
#  2. Fix ownership of wp-content so www-data can write
set -e

WPC=/var/www/html/wp-config.php

# 1. FS_METHOD=direct (idempotent)
if [ -f "$WPC" ]; then
  cp "$WPC" "$WPC.bak"
  if grep -q "FS_METHOD" "$WPC"; then
    echo "FS_METHOD already present"
  else
    DEFINE_LINE="define('FS_METHOD','direct');"
    awk -v line="$DEFINE_LINE" '
      /stop editing/ && !done {print line; done=1}
      /^require/ && !done {print line; done=1}
      {print}
    ' "$WPC" > "$WPC.new"
    mv "$WPC.new" "$WPC"
  fi
  echo "--- FS_METHOD line ---"
  grep -n "FS_METHOD" "$WPC"
else
  echo "wp-config.php not found at $WPC (unconfigured site?)"
fi

# 2. Ownership: make wp-content (themes/plugins/uploads) writable by www-data
chown -R www-data:www-data /var/www/html/wp-content
find /var/www/html/wp-content -type d -exec chmod 755 {} \;
find /var/www/html/wp-content -type f -exec chmod 644 {} \;

echo "--- ownership after fix ---"
for d in wp-content wp-content/themes wp-content/plugins wp-content/uploads; do
  if [ -e "/var/www/html/$d" ]; then
    stat -c '%U:%G %a %n' "/var/www/html/$d"
  else
    echo "(not yet present: $d)"
  fi
done
echo "FIX_APPLIED"