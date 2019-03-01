# This is just a hack to avoid pycodestyle complaining about
#  E402 module level import not at top of file
# when loading matplotlib with Agg backend, which has to be
# procedurally configured after importing matplotlib and before
# mporting matplotlib.pyplot.
# Thanks to https://stackoverflow.com/questions/39305810

import matplotlib
matplotlib.use('Agg')
