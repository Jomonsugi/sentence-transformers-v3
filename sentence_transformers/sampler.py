from itertools import accumulate, cycle
from typing import List, TYPE_CHECKING
import logging

from torch.utils.data import BatchSampler, SubsetRandomSampler
import torch

if TYPE_CHECKING:
    from sentence_transformers.trainer import SentenceTransformerTrainer

logger = logging.getLogger(__name__)


class RoundRobinBatchSampler:
    def __init__(
        self,
        lengths: List[int],
        batch_size: int,
        drop_last: bool = False,
        seed: int = 0,
        shuffle: bool = True,
        trainer: "SentenceTransformerTrainer" = None,
    ):
        self.lengths = lengths
        accumulated = list(accumulate(self.lengths))
        self.ranges = [(start, end) for start, end in zip([0] + accumulated, accumulated)]

        self.seed = seed
        self.shuffle = shuffle
        self.drop_last = drop_last
        self.batch_size = batch_size
        self.trainer = trainer

        self.epoch = 0

    def __iter__(self):
        # deterministically shuffle based on epoch and seed
        g = torch.Generator()
        g.manual_seed(self.seed + self.epoch)

        batch_samplers = [
            iter(
                BatchSampler(
                    SubsetRandomSampler(range(start, end), generator=g) if self.shuffle else range(start, end),
                    self.batch_size,
                    self.drop_last,
                )
            )
            for (start, end) in self.ranges
        ]

        for dataset_idx in cycle(range(len(batch_samplers))):
            try:
                yield next(batch_samplers[dataset_idx])
                if self.trainer and self.trainer.training_with_dataset_dict:
                    self.trainer.dataset_name = self.trainer.dataset_names[dataset_idx]

            except StopIteration:
                # current iterator is apparently exhausted
                break

    def set_epoch(self, epoch: int):
        self.epoch = epoch

    def __len__(self) -> int:
        if self.drop_last:
            return min([length // self.batch_size for length in self.lengths]) * len(self.lengths)
        else:
            return min([(length + self.batch_size - 1) // self.batch_size for length in self.lengths]) * len(
                self.lengths
            )


class ProportionalBatchSampler:
    def __init__(
        self,
        lengths: List[int],
        batch_size: int,
        drop_last: bool = False,
        seed: int = 0,
        shuffle: bool = True,
        trainer: "SentenceTransformerTrainer" = None,
    ):
        self.lengths = lengths
        accumulated = list(accumulate(self.lengths))
        self.ranges = [(start, end) for start, end in zip([0] + accumulated, accumulated)]

        self.seed = seed
        self.shuffle = shuffle
        self.drop_last = drop_last
        self.batch_size = batch_size
        self.trainer = trainer

        self.epoch = 0

    def __iter__(self):
        # deterministically shuffle based on epoch and seed
        g = torch.Generator()
        g.manual_seed(self.seed + self.epoch)

        batch_samplers = [
            BatchSampler(
                SubsetRandomSampler(range(start, end), generator=g) if self.shuffle else range(start, end),
                self.batch_size,
                self.drop_last,
            )
            for (start, end) in self.ranges
        ]

        lengths = [len(sampler) for sampler in batch_samplers]
        indices = [idx for idx, length in enumerate(lengths) for _ in range(length)]
        sampler = SubsetRandomSampler(indices, generator=g)

        batch_samplers = [iter(sampler) for sampler in batch_samplers]
        for dataset_idx in sampler:
            yield next(batch_samplers[dataset_idx])
            if self.trainer and self.trainer.training_with_dataset_dict:
                self.trainer.dataset_name = self.trainer.dataset_names[dataset_idx]

    def set_epoch(self, epoch: int):
        self.epoch = epoch

    def __len__(self) -> int:
        if self.drop_last:
            return sum([length // self.batch_size for length in self.lengths])
        else:
            return sum([(length + self.batch_size - 1) // self.batch_size for length in self.lengths])
