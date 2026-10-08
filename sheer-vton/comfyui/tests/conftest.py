import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

try:  # the nodes need torch only to wrap arrays; a stub stands in where torch is not installed
    import torch  # noqa: F401
except ImportError:
    torch = types.ModuleType('torch')

    class Tensor(np.ndarray):
        def detach(self):
            return self

        def cpu(self):
            return self

        def numpy(self):
            return np.asarray(self)

    torch.Tensor = Tensor
    torch.from_numpy = lambda a: np.asarray(a).view(Tensor)
    sys.modules['torch'] = torch
