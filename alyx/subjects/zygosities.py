ZYGOSITY_RULES = (
    ('CtTa', 'Camk2a-tTa', (('tTA', '+'),
                            ('-tTA', '-/-'))),

    ('Pv', 'Pv-Cre', (('Cre,WT', '+/-'),
                      ('Cre,-WT', '+/+'),
                      ('-Cre', '-/-'))),

    ('TetO', 'TetO-G6s', (('TRE,WT', '+/-'),
                          ('TRE,-WT', '+/+'),
                          ('-TRE', '-/-'))),

    ('TetO.CtTa', 'TetO-G6s', (('TRE', '+/-'),
                               ('-TRE', '-/-'))),

    ('TetO.CtTa', 'Camk2a-tTa', (('tTA', '+/-'),
                                 ('-tTA', '-/-'))),
)
