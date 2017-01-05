#/bin/bash
grep ",0.0,0.0" $1 | grep -vE "Staff|Guest" | column -t -s,
