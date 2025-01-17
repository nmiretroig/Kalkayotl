
"""
Elson, Fall and Freeman distance prior. Inspired by Ellson et al. 1987
"""
__all__ = ['eff', 'EFF']
import numpy as np
import theano.tensor as tt

from pymc3.util import get_variable_name
from pymc3.distributions.dist_math import bound
from pymc3.distributions.continuous import PositiveContinuous,assert_negative_support
from pymc3.distributions.distribution import draw_values, generate_samples

from scipy.stats import rv_continuous
from scipy.optimize import root_scalar
from scipy.special import gamma as gamma_function
import scipy.integrate as integrate
from scipy.special import hyp2f1

#=============== EFF generator ===============================
class eff_gen(rv_continuous):
	"EFF distribution"
	""" This probability density function is defined for x>0"""
	def _pdf(self,x,r0,rc,gamma):

		n0 = (np.sqrt(np.pi)*rc*gamma_function(0.5*(gamma-1.))/(2*gamma_function(gamma/2.))
				+ r0*hyp2f1(0.5,0.5*gamma,1.5,-(r0/rc)**2))
		nx = (1.+((x-r0)/rc)**2)**(-0.5*gamma)
		return nx/n0

	def _cdf(self,x,r0,rc,gamma):
		a = r0*hyp2f1(0.5,0.5*gamma,1.5,-(r0/rc)**2)
		b = (x-r0)*hyp2f1(0.5,0.5*gamma,1.5,-((x-r0)/rc)**2) 
		c = np.sqrt(np.pi)*rc*gamma_function(0.5*(gamma-1.))/(2*gamma_function(gamma/2.))
		return (b+a)/(c + a)
				

	def _rvs(self,r0,rc,gamma):
		#---- Setting 0.99 and 100*rc works well for gamma > 2----
		sz, rndm = self._size, self._random_state
		u = rndm.uniform(0.0,0.99,size=sz)

		v = np.zeros_like(u)

		for i in range(sz[0]):
			try:
				sol = root_scalar(lambda x : self._cdf(x,r0,rc,gamma) - u[i],
				bracket=[0.0,r0+100.*rc],
				method='brentq')
			except Exception as e:
				print(u[i])
				print(self._cdf(0.0,r0,rc,gamma))
				print(self._cdf(r0+100.*rc,r0,rc,gamma))
				raise
			v[i] = sol.root
			sol  = None
		return v

eff = eff_gen(a=0.0,name='EFF')
#===============================================================


class EFF(PositiveContinuous):
	R"""
	Elson, Fall and Freeman log-likelihood.
	The pdf of this distribution is
	.. math::
	   EFF(x|r_0,r_c,\gamma)=\frac{\Gamma(\gamma/2)}
	   {\sqrt{\pi}\cdot r_c \cdot \Gamma(\frac{\gamma-1}{2})}
	   \left[ 1 + \left(\frac{x-r_0}{r_c}\right)^2\right]^{-\frac{\gamma}{2}}

	.. note::
	   This probability distribution function is defined from -infty to infty
	   In contrast to the scipy defined above. We do this because Theano does not
	   include the HyperGeometric 2F1 function. :'(
	   
	========  ==========================================
	Support   :math:`x \in [-\infty, \infty)`
	========  ==========================================
	Parameters
	----------
	loc: float
		Location parameter :math:`loc` (``loc`` > 0) .

	scale: float
		Scale parameter :math:`scale` (``scale`` > 0) .

	gamma: float
		Slope parameter :math:`\gamma` (``\gamma`` > 1) .

	Examples
	--------
	.. code-block:: python
		with pm.Model():
			x = pm.EFF('x', loc=100,scale=10,gamma=2)
	"""

	def __init__(self, r0=None,rc=None,gamma=None, *args, **kwargs):

		super().__init__(*args, **kwargs)

		self.r0    = r0    = tt.as_tensor_variable(r0)
		self.rc    = rc    = tt.as_tensor_variable(rc)
		self.gamma = gamma = tt.as_tensor_variable(gamma)

		self.mean = self.r0
		# self.variance = (1. - 2 / np.pi) / self.tau

		assert_negative_support(rc, 'rc', 'EFF')

	def random(self, point=None, size=None):
		"""
		Draw random values from HalfNormal distribution.
		Parameters
		----------
		point : dict, optional
			Dict of variable values on which random values are to be
			conditioned (uses default point if not specified).
		size : int, optional
			Desired size of random sample (returns one sample if not
			specified).
		Returns
		-------
		array
		"""
		r0,rc,gamma = draw_values([self.r0,self.rc,self.gamma], 
									point=point,size=size)
		return generate_samples(eff.rvs, r0=r0,rc=rc,gamma=gamma,
								dist_shape=self.shape,
								size=size)

	def logp(self, value):
		"""
		Calculate log-probability of EFF distribution at specified value.
		Parameters
		----------
		value : numeric
			Value(s) for which log-probability is calculated. If the log probabilities for multiple
			values are desired the values must be provided in a numpy array or theano tensor
		Returns
		-------
		TensorVariable
		"""
		r0     = self.r0
		rc     = self.rc
		gamma  = self.gamma

		n0 = tt.sqrt(np.pi)*rc*tt.gamma(0.5*(gamma-1.))

		log_d  = -0.5*gamma*tt.log(1.+ ((value - r0)/rc)**2) + tt.gammaln(0.5*gamma) - tt.log(n0)
		return bound(log_d,value >= 0.,r0 > 0.,rc > 0.,gamma > 1.)

	def _repr_latex_(self, name=None, dist=None):
		if dist is None:
			dist = self
		r0    = dist.r0
		rc    = dist.rc
		gamma = dist.gamma
		name = r'\text{%s}' % name
		return r'${} \sim \text{{EFF}}(\mathit{{loc}}={},\mathit{{scale}}={},\mathit{{\gamma}}={})$'.format(name,
					get_variable_name(r0),get_variable_name(rc),get_variable_name(gamma))

###################################################### TEST ################################################################################

import matplotlib
matplotlib.use('PDF')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import scipy.stats as st

def test_numpy(n=1000,r0=300.,rc=17.,gamma=2):

	# ----- Generate samples ---------
	s = eff.rvs(r0=100,rc=2.,gamma=2.,size=n)
	#------ grid -----
	x = np.linspace(0,r0+100.*rc,1000)
	range_dist = (r0-10*rc,r0+10*rc)
	y = eff.pdf(x,r0=r0,rc=rc,gamma=gamma)
	z = eff.cdf(x,r0=r0,rc=rc,gamma=gamma)

	pdf = PdfPages(filename="Test_EFF_numpy.pdf")
	plt.figure(0)
	plt.hist(s,bins=100,range=range_dist,density=True,color="grey",label="Samples")
	plt.plot(x,y,color="black",label="PDF")
	plt.xlim(range_dist)
	plt.legend()
	
	#-------------- Save fig --------------------------
	pdf.savefig(bbox_inches='tight')
	plt.close(0)

	plt.figure(1)
	plt.plot(x,z,color="black",label="CDF")
	plt.legend()
	
	#-------------- Save fig --------------------------
	pdf.savefig(bbox_inches='tight')
	plt.close(1)
	
	pdf.close()
	
	
if __name__ == "__main__":
	test_numpy()
	print("numpy version OK")