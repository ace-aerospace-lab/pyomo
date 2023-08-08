# =================
# Import Statements
# =================
import pyomo.environ as pyo
from pyomo.environ import units
from pyomo.contrib.edi import Formulation
from pyomo.contrib.edi import BlackBoxFunctionModel

# ===================
# Declare Formulation
# ===================
f = Formulation()

# =================
# Declare Variables
# =================
x = f.Variable(name='x', guess=1.0, units='m', description='The x variable')
y = f.Variable(name='y', guess=1.0, units='m', description='The y variable')
z = f.Variable(name='z', guess=1.0, units='m^2', description='Model output')

# =================
# Declare Constants
# =================
c = f.Constant(name='c', value=1.0, units='', description='A constant c', size=2)

# =====================
# Declare the Objective
# =====================
f.Objective(c[0] * x + c[1] * y)


# ===================
# Declare a Black Box
# ===================
class UnitCircle(BlackBoxFunctionModel):
    def __init__(self):  # The initialization function
        # Initialize the black box model
        super().__init__()

        # A brief description of the model
        self.description = 'This model evaluates the function: z = x**2 + y**2'

        # Declare the black box model inputs
        self.inputs.append(name='x', units='ft', description='The x variable')
        self.inputs.append(name='y', units='ft', description='The y variable')

        # Declare the black box model outputs
        self.outputs.append(
            name='z', units='ft**2', description='Resultant of the unit circle'
        )

        # Declare the maximum available derivative
        self.availableDerivative = 1

    def BlackBox(self, x, y):  # The actual function that does things
        # Converts to correct units then casts to float
        x = pyo.value(units.convert(x, self.inputs['x'].units))
        y = pyo.value(units.convert(y, self.inputs['y'].units))

        z = x**2 + y**2  # Compute z
        dzdx = 2 * x  # Compute dz/dx
        dzdy = 2 * y  # Compute dz/dy

        z *= units.ft**2
        dzdx *= units.ft  # units.ft**2 / units.ft
        dzdy *= units.ft  # units.ft**2 / units.ft

        return z, [dzdx, dzdy]  # return z, grad(z), hess(z)...


# =======================
# Declare the Constraints
# =======================
f.ConstraintList([[z, '==', [x, y], UnitCircle()], z <= 1 * units.m**2])
<<<<<<< HEAD

# =============================================
# Run the black box (improves coverage metrics)
# =============================================
uc = UnitCircle()
bbo = uc.BlackBox(0.5 * units.m, 0.5 * units.m)
=======
>>>>>>> parent of f76f4974b (addressing concerns in PR)
