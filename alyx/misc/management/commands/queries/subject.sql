SELECT subjects_subject.id,
subjects_subject.nickname,
subjects_subject.sex,
subjects_subject.birth_date,
subjects_subject.death_date,
subjects_subject.implant_weight,
subjects_subject.description,
subjects_subject.ear_mark,
subjects_breedingpair.name AS breeding_pair,
subjects_line.name AS line,
subjects_litter.name AS litter,
misc_labmember.username AS responsible_user,
subjects_source.name AS source,
subjects_species.nickname AS species,
subjects_strain.name AS strain,
subjects_subject.wean_date,
subjects_subject.actual_severity,
subjects_subject.adverse_effects,
subjects_subject.cull_method,
subjects_subject.json,
subjects_subject.request_id
FROM subjects_subject
LEFT JOIN subjects_line on subjects_subject.line_id=subjects_line.id
LEFT JOIN misc_labmember on subjects_subject.responsible_user_id=misc_labmember.id
LEFT JOIN subjects_litter on subjects_subject.litter_id=subjects_litter.id
LEFT JOIN subjects_breedingpair on subjects_litter.breeding_pair_id=subjects_breedingpair.id
LEFT JOIN subjects_source on subjects_subject.source_id=subjects_source.id
LEFT JOIN subjects_species on subjects_subject.species_id=subjects_species.id
LEFT JOIN subjects_strain on subjects_subject.strain_id=subjects_strain.id
ORDER BY line, subjects_subject.birth_date DESC, subjects_subject.nickname DESC
