SELECT subjects_subjectrequest.id,
subjects_subjectrequest.json,
subjects_subjectrequest.count,
subjects_subjectrequest.date_time,
subjects_subjectrequest.due_date,
subjects_subjectrequest.description,
subjects_line.name AS line_name,
misc_labmember.username AS username
FROM subjects_subjectrequest
LEFT JOIN subjects_line on subjects_subjectrequest.line_id=subjects_line.id
LEFT JOIN misc_labmember on subjects_subjectrequest.user_id=misc_labmember.id
