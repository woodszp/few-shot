import unittest
from torch.utils.data import DataLoader
import torch

from few_shot.few_shot import compute_prototypes, NShotSampler, matching_net_predictions
from few_shot.datasets import DummyDataset, OmniglotDataset, MiniImageNet
from few_shot.models import get_few_shot_encoder
from few_shot.utils import pairwise_distances


class TestProtoNets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = DummyDataset(samples_per_class=1000, n_classes=20)

    def _test_n_k_q_combination(self, n, k, q):
        n_shot_taskloader = DataLoader(self.dataset,
                                       batch_sampler=NShotSampler(self.dataset, 100, n, k, q))

        # Load a single n-shot, k-way task
        for batch in n_shot_taskloader:
            x, y = batch
            break

        support = x[:n * k]
        support_labels = y[:n * k]
        prototypes = compute_prototypes(support, k, n)

        # By construction the second feature of samples from the
        # DummyDataset is equal to the label.
        # As class prototypes are constructed from the means of the support
        # set items of a particular class the value of the second feature
        # of the class prototypes should be equal to the label of that class.
        for i in range(k):
            self.assertEqual(
                support_labels[i * n],
                prototypes[i, 1],
                'Prototypes computed incorrectly!'
            )

    def test_compute_prototypes(self):
        test_combinations = [
            (1, 5, 5),
            (5, 5, 5),
            (1, 20, 5),
            (5, 20, 5)
        ]

        for n, k, q in test_combinations:
            self._test_n_k_q_combination(n, k, q)

    def test_create_model(self):
        # Check output of encoder has shape specified in paper
        encoder = get_few_shot_encoder(num_input_channels=1).float()
        omniglot = OmniglotDataset('background')
        self.assertEqual(
            encoder(omniglot[0][0].unsqueeze(0).float()).shape[1],
            64,
            'Encoder network should produce 64 dimensional embeddings on Omniglot dataset.'
        )

        encoder = get_few_shot_encoder(num_input_channels=3).float()
        omniglot = MiniImageNet('background')
        self.assertEqual(
            encoder(omniglot[0][0].unsqueeze(0).float()).shape[1],
            1600,
            'Encoder network should produce 1600 dimensional embeddings on miniImageNet dataset.'
        )


class TestMatchingNets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = DummyDataset(samples_per_class=1000, n_classes=20)

    def _test_n_k_q_combination(self, n, k, q):
        n_shot_taskloader = DataLoader(self.dataset,
                                       batch_sampler=NShotSampler(self.dataset, 100, n, k, q))

        # Load a single n-shot, k-way task
        for batch in n_shot_taskloader:
            x, y = batch
            break

        # Take just dummy label features and a little bit of noise
        # So distances are never 0
        support = x[:n * k, 1:]
        queries = x[n * k:, 1:]
        support += torch.rand_like(support)
        queries += torch.rand_like(queries)

        distances = pairwise_distances(queries, support, 'cosine')

        # Calculate "attention" as softmax over distances
        attention = (-distances).softmax(dim=1).cuda()

        y_pred = matching_net_predictions(attention, n, k, q)

        self.assertEqual(
            y_pred.shape,
            (q * k, k),
            'Matching Network predictions must have shape (q * k, k).'
        )

        y_pred_sum = y_pred.sum(dim=1)
        self.assertTrue(
            torch.all(
                torch.isclose(y_pred_sum, torch.ones_like(y_pred_sum).double())
            ),
            'Matching Network predictions probabilities must sum to 1 for each '
            'query sample.'
        )

    def test_matching_net_predictions(self):
        test_combinations = [
            (1, 5, 5),
            (5, 5, 5),
            (1, 20, 5),
            (5, 20, 5)
        ]

        for n, k, q in test_combinations:
            self._test_n_k_q_combination(n, k, q)



