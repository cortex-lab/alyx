SELECT subjects_litter.id,
subjects_litter.name,
subjects_litter.description,
subjects_litter.birth_date,
subjects_breedingpair.name AS breeding_pair,
subjects_line.name AS line,
subjects_litter.json
FROM subjects_litter
LEFT JOIN subjects_breedingpair on subjects_litter.breeding_pair_id=subjects_breedingpair.id
LEFT JOIN subjects_line on subjects_litter.line_id=subjects_line.id
