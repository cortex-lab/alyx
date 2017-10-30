ZYGOSITY_RULES = (
    ('N.KHA', 'Ntsr1-Cre', (('Cre', '+/-'),  # need to check on this one too.
                            ('-Cre', '-/-'))),

    ('Thy18.Pv', 'Thy18-ChR2', (('YFP', '+'),
                                ('-YFP', '-/-'))),

    ('RCL.Vg', 'Ai95-G6f', (('GFP', '+/-'),
                            ('-GFP', '-/-'))),

    ('RCL.Vg', 'Vglut1-Cre', (('Cre', '+/-'),
                              ('-Cre', '-/-'))),

    ('RCLcg.Vg', 'Ai95-G6f', (('eGFP', '+/-'),
                              ('-eGFP', '-/-'))),

    ('RCLcg.Vg', 'Vglut1-Cre', (('Cre', '+/-'),
                                ('-Cre', '-/-'))),

    ('Ai78.CtTa', 'Camk2a-tTa', (('tTA', '+/-'),
                                 ('-tTA', '-/-'))),

    ('Ai78.CtTa', 'Ai78-VSFP', (('VSFP', '+/-'),  # I think I need to ask about this one...
                                ('-VSFP', '-/-'))),

    ('Vip', 'Vip-Cre', (('Cre,Vip WT', '+/-'),
                        ('Cre,-Vip WT', '+/+'),
                        ('-Cre', '-/-'))),

    ('Vg', 'Vglut1-Cre', (('Cre,WT', '+/-'),
                          ('Cre,-WT', '+/+'),
                          ('-Cre', '-/-'))),

    ('Thy18', 'Thy18-ChR2', (('YFP', '+'),
                             ('-YFP', '-/-'))),

    ('TdTom', 'TdTom-RFP', (('tdRFP,ROSA WT', '+/-'),
                            ('tdRFP,-ROSA WT', '+/+'),
                            ('-tdRFP', '-/-'))),

    ('Sst', 'Sst-Cre', (('Cre,Sst WT', '+/-'),
                        ('Cre,-Sst WT', '+/+'),
                        ('-Cre', '-/-'))),

    # note I think spreadsheet has a typo here, currently has Cre and Sst WT,
    # but I think it should be these
    ('Snap', 'Snap25-G6s', (('GFP,WT', '+/-'),
                            ('GFP,-WT', '+/+'),
                            ('-GFP', '-/-'))),

    ('RCL', 'Ai95-G6f', (('eGFP,WT', '+/-'),
                         ('eGFP,-WT', '+/+'),
                         ('-eGFP', '-/-'))),

    ('RCLcg', 'Ai95-G6f', (('eGFP,WT', '+/-'),
                           ('eGFP,-WT', '+/+'),
                           ('-eGFP', '-/-'))),

    ('Rasgrf', 'Rasgrf-Cre', (('Rasgrf Cre,Rasgrf WT', '+/-'),
                              ('Rasgrf Cre,-Rasgrf WT', '+/+'),
                              ('-Rasgrf Cre', '-/-'))),

    ('KHA', 'Vglut1-MD', (('Vglut1 MD,Vglut1 WT', '+/-'),
                          ('Vglut1 MD,-Vglut1 WT', '+/+'),
                          ('-Vglut1 MD', '-/-'))),

    ('Gad', 'Gad-Cre', (('Cre,WT', '+/-'),
                        ('Cre,-WT', '+/+'),
                        ('-Cre', '-/-'))),

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

    ('Ai32', 'Ai32-ChR2', (('ChR2-YFP,WT', '+/-'),
                           ('ChR2-YFP,-WT', '+/+'),
                           ('-ChR2-YFP', '-/-'))),

    ('DA', 'DAT-Cre', (('Cre,WT', '+/-'),
                       ('Cre,-WT', '+/+'),
                       ('-Cre', '-/-'))),

    ('Drd', 'Drd1a-Cre', (('Cre,WT', '+/-'),
                          ('Cre,-WT', '+/+'),
                          ('-Cre', '-/-'))),

    ('Emx', 'Emx1-Cre', (('Cre,WT', '+/-'),
                         ('Cre,-WT', '+/+'),
                         ('-Cre', '-/-'))),

    ('Ai148', 'Ai148-G6f', (('GFP,WT', '+/-'),
                            ('GFP,-WT', '+/+'),
                            ('-GFP', '-/-'))),

    ('Ai148.Vg', 'Ai148-G6f', (('eGFP', '+/-'),
                               ('-eGFP', '-/-'))),

    ('Ai148.Vg', 'Vglut1-Cre', (('Cre', '+/-'),
                                ('-Cre', '-/-'))),

)
