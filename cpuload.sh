interval=0.1; ##loop interval in seconds

##so settings below
lCpus=(); ##store last readings
lCount=0; ## loop counter

while :; do {

    cCpu=(); ##current cpu
    cCpus=(); ##all cpus
    values=$(grep -E "cpu[0-9]+\s" /proc/stat);
    for value in $values; do {
        if [[ $value =~ ^cpu[0-9]+ ]]; then
            if [[ ${#cCpu[@]} > 0 ]]; then
                cCpus[${cCpu[1]}]="${cCpu[@]}"
            fi

            cCpu[0]=$value; ##name
            cCpu[1]=${#cCpus[@]}; ##cpu index
            cCpu[2]=0; ##cpu idle ticks
            cCpu[3]=0; ##cpu busy ticks
            i=0; ## column index

        else
            ((i=i+1));
            if ([ $i == 4 ] || [ $i == 5 ]); then
                # position 4 is the idle, position 5 is the i/o wait (also idle introduced 2.5.41) src https://www.idnt.net/en-US/kb/941772
                ((cCpu[2]=cCpu[2] + value));
            else
                ((cCpu[3]=cCpu[3] + value));
            fi
        fi
    } done

    ##include the last cpu
    cCpus[${cCpu[1]}]="${cCpu[@]}"

    output="Loop $lCount";
    x=0;
    for cpu in "${cCpus[@]}"; do {
        if [[ $lCount > 0 ]]; then
       
            cCpu=($cpu);
            lCpu=(${lCpus[$x]});
            dTotal=$(((${cCpu[2]} + ${cCpu[3]}) - (${lCpu[2]} + ${lCpu[3]})));
            dUsed=$((dTotal - (${cCpu[2]} - ${lCpu[2]})));
            if [[ $dTotal == 0 ]]; then
                dTotal=1; ##dividing by 0 is never a good idea
            fi
            output="$output, ${cCpu[0]}: $((100 * dUsed / dTotal))%";
        fi
        ##store the reading so we can do a delta next round
        lCpus[$x]=$cpu;
        ((x=x+1));
       
    } done
   
    if [[ $lCount > 0 ]]; then
        echo $output;
    fi
   
    sleep $interval;
    ((lCount=lCount+1));
   
} done
