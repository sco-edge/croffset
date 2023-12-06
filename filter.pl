#!/usr/bin/perl

my %data;
my $num = $ARGV[1];

open my $trace, $ARGV[0] or die "Need a file\n";
while (my $line = <$trace>) {
    my @fields = split ",", $line;
    $data{$fields[0]}++ if $fields[0] =~ /0x/;
}

my @keys = (reverse sort { $data{$a} <=> $data{$b} } keys %data);
# foreach $key (@keys) {
#     print "$key, $data{$key}\n";
# }
close $trace;

foreach (0..$num-1) {
    open my $trace, $ARGV[0] or die "Need a file\n";
    open(FH, '>', "f$_." . $ARGV[0]) or die "Failed to open an output file\n";
    while (my $line = <$trace>) {
        my @fields = split ",", $line;
        print FH $line if $fields[0] =~ /$keys[$_]/;
    }
    close $trace;
    close FH;
}

# open(FH, '>', 'f.' . $ARGV[0]) or die "Failed to open an output file\n";
# while (my $line = <$trace>) {
#     my @fields = split ",", $line;
#     foreach (0..$num-1) {
#         print FH $line if $fields[0] =~ /$keys[$_]/;
#     }
#     # print $line if $fields[0] =~ /$maxkey/;
#     # print FH $line if $fields[0] =~ /$maxkey/;
# }