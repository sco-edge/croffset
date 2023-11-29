#!/usr/bin/perl

my %data;
my $maxkey;
my $maxvalue;

open my $trace, $ARGV[0] or die "Need a file\n";
while (my $line = <$trace>) {
    my @fields = split ",", $line;
    $data{$fields[0]}++ if $fields[0] =~ /0x/;
}

while (($k,$v) = each %data) {
    if ($maxvalue <= $v) {
        $maxvalue = $v;
        $maxkey = $k;
    }
}
close $trace;

open my $trace, $ARGV[0] or die "Need a file\n";
open(FH, '>', 'f.' . $ARGV[0]) or die "Failed to open an output file\n";
while (my $line = <$trace>) {
    my @fields = split ",", $line;
    # print $line if $fields[0] =~ /$maxkey/;
    print FH $line if $fields[0] =~ /$maxkey/;
}