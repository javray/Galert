#!/bin/sh

jarsigner -verbose -keystore ../my-release-key.keystore bin/Galert-unsigned.apk alias_name
jarsigner -verify bin/Galert-unsigned.apk
rm bin/Galert.apk
zipalign -v 4 bin/Galert-unsigned.apk bin/Galert.apk

