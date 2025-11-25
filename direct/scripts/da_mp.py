#!/usr/bin/env python3

import logging

from shootout import mkargparser, da_mp_main, logger


if __name__ == '__main__':
    parser = mkargparser()
    args = parser.parse_args()

    log_level = logging.WARNING
    if args.verbose:
        log_level = logging.INFO
    if args.debug:
        log_level = logging.DEBUG

    log_file = 'da_mp.log'
    LOGGING_FORMAT = '[%(asctime)s][%(levelname)s][%(module)s][%(funcName)s] %(message)s'

    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(log_level)
    fmt = logging.Formatter(LOGGING_FORMAT)
    fh.setFormatter(fmt)
    logging.basicConfig(level=log_level, handlers=[fh])
    logger.addHandler(fh)

    da_mp_main(use_cache=args.use_cache, nprocs=args.nprocs)
